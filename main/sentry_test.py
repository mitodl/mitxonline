"""Tests for Sentry event scrubbing."""

import json
import logging
from dataclasses import dataclass

import pytest
import sentry_sdk
from django.test import override_settings
from django.urls import path
from sentry_sdk.data_collection import _map_from_send_default_pii, _resolve_explicit
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.transport import Transport

from main.sentry import (
    EXPORT_COMPLIANCE_USER_TAG,
    before_send,
    before_send_transaction,
    build_data_collection,
    build_event_scrubber,
    init_sentry,
    scrub_export_compliance_event,
    scrub_pg_detail,
    scrub_pg_details,
    scrub_secret_values,
)
from main.urls import urlpatterns as main_urlpatterns
from users.factories import UserFactory

# A real MITXONLINE-6PK exception value, with the learner identifiers replaced.
PG_INTEGRITY_ERROR = (
    'null value in column "name" of relation "users_user" violates not-null '
    "constraint\n"
    "DETAIL:  Failing row contains (1863408, , 2026-08-07 18:38:14.503726+00, f, "
    "learner@example.invalid, learner@example.invalid, null, f, t, "
    "12d7dfc5-6f84-46db-9383-2d7079434173, 1863408, learner@example.invalid, f)."
)
PG_PRIMARY_MESSAGE = (
    'null value in column "name" of relation "users_user" violates not-null constraint'
)


class FakeTransport(Transport):
    """Collect outgoing events instead of sending them."""

    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        self.events.extend(
            item.payload.json
            for item in envelope.items
            if item.type in ("event", "transaction")
        )


@pytest.fixture
def sentry_transport():
    """Initialize the real SDK with before_send, and detach it afterwards."""
    transport = FakeTransport()
    sentry_sdk.init(
        dsn="https://k@o0.ingest.sentry.io/0",
        transport=transport,
        before_send=before_send,
        default_integrations=False,
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        ],
    )
    yield transport
    sentry_sdk.get_global_scope().set_client(None)


def test_detail_line_is_truncated():
    """The row echo goes; the primary error that names the failure stays."""
    scrubbed = scrub_pg_detail(PG_INTEGRITY_ERROR)
    assert scrubbed.startswith(PG_PRIMARY_MESSAGE)
    assert "learner@example.invalid" not in scrubbed
    assert "12d7dfc5-6f84-46db-9383-2d7079434173" not in scrubbed


def test_escaped_detail_line_is_truncated():
    """repr() turns the newline into a literal backslash-n; that form goes too."""
    scrubbed = scrub_pg_detail(repr(Exception(PG_INTEGRITY_ERROR)))
    assert PG_PRIMARY_MESSAGE in scrubbed
    assert "learner@example.invalid" not in scrubbed


def test_message_without_detail_is_unchanged():
    """A message with no DETAIL line passes through untouched."""
    message = "connection to server failed"
    assert scrub_pg_detail(message) == message


def test_hint_and_context_after_detail_are_dropped():
    """HINT and CONTEXT follow DETAIL and can quote row data too."""
    text = "boom\nDETAIL:  row data\nHINT:  try again\nCONTEXT:  SQL statement"
    scrubbed = scrub_pg_detail(text)
    assert "row data" not in scrubbed
    assert "try again" not in scrubbed
    assert "SQL statement" not in scrubbed


def test_scrubs_exception_values_logentry_and_message():
    """Every place the SDK can put an error string is covered."""
    event = {
        "exception": {"values": [{"value": PG_INTEGRITY_ERROR}]},
        "logentry": {
            "message": PG_INTEGRITY_ERROR,
            "formatted": PG_INTEGRITY_ERROR,
        },
        "message": PG_INTEGRITY_ERROR,
    }
    scrub_pg_details(event)
    assert "learner@example.invalid" not in repr(event)


def test_before_send_scrubs_the_event():
    """The scrub is wired into the before_send hook, not just callable."""
    event = {"exception": {"values": [{"value": PG_INTEGRITY_ERROR}]}}
    assert "learner@example.invalid" not in repr(before_send(event, {}))


def test_scrubs_breadcrumb_messages():
    """LoggingIntegration records the log message as a breadcrumb."""
    event = {
        "breadcrumbs": {
            "values": [
                {
                    "type": "log",
                    "category": "django_scim.views",
                    "message": PG_INTEGRITY_ERROR,
                }
            ]
        }
    }
    scrub_pg_details(event)
    assert "learner@example.invalid" not in repr(event)


def test_scrubs_logentry_params():
    """logger.error("...: %s", exc) puts the repr'd exception in logentry.params."""
    event = {
        "logentry": {
            "message": "Unable to complete SCIM call: %s",
            "formatted": "Unable to complete SCIM call: " + PG_INTEGRITY_ERROR,
            "params": [repr(Exception(PG_INTEGRITY_ERROR))],
        }
    }
    scrub_pg_details(event)
    assert "learner@example.invalid" not in repr(event)


def test_scrubs_captured_frame_locals():
    """include_local_variables defaults to True, so repr'd frame vars carry it."""
    event = {
        "exception": {
            "values": [
                {
                    "value": "boom",
                    "stacktrace": {
                        "frames": [
                            {
                                "function": "save",
                                "vars": {
                                    "exc": repr(Exception(PG_INTEGRITY_ERROR)),
                                    "retries": 3,
                                },
                            }
                        ]
                    },
                }
            ]
        }
    }
    scrub_pg_details(event)
    assert "learner@example.invalid" not in repr(event)
    frame = event["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert frame["vars"]["retries"] == 3


def test_walk_preserves_non_string_leaves():
    """The walk must not coerce timestamps, ints or None into strings."""
    event = {
        "timestamp": 1757345533.179,
        "level": "error",
        "extra": {"count": 42, "missing": None, "flag": True},
        "message": PG_INTEGRITY_ERROR,
    }
    scrub_pg_details(event)
    assert event["timestamp"] == 1757345533.179
    assert event["extra"] == {"count": 42, "missing": None, "flag": True}
    assert "learner@example.invalid" not in event["message"]


def test_real_sdk_scrubs_params_and_local_variables(sentry_transport):
    """Go through the real SDK, which repr()s params and locals before before_send."""

    def save():
        exc = Exception(PG_INTEGRITY_ERROR)
        raise exc

    try:
        save()
    except Exception as e:  # noqa: BLE001
        logging.getLogger("x").error("Unable to save: %s", e)  # noqa: TRY400
        sentry_sdk.capture_exception(e)
    sentry_sdk.flush()

    assert len(sentry_transport.events) == 2
    for event in sentry_transport.events:
        assert "learner@example.invalid" not in json.dumps(event)


OIDC_SECRET = "oidc-client-secret-value"  # noqa: S105
LEARNER_USER = {"id": "42", "email": "learner@example.invalid", "username": "ada"}


@dataclass
class IdentityProviderPayload:
    """Stands in for a Keycloak representation object, which the SDK repr()s."""

    alias: str
    config: dict


@pytest.mark.parametrize(
    "text",
    [
        json.dumps({"clientId": "partner", "clientSecret": OIDC_SECRET}),
        repr(json.dumps({"client_secret": OIDC_SECRET}).encode()),
        repr({"config": {"clientSecret": OIDC_SECRET}}),
        f"IdentityProviderPayload(client_secret='{OIDC_SECRET}')",
        repr(repr(json.dumps({"clientSecret": OIDC_SECRET}))),
    ],
)
def test_secret_values_are_blanked_in_strings(text):
    """JSON, repr()d bytes and dicts, keyword reprs and escaped nestings."""
    scrubbed = scrub_secret_values(text)
    assert OIDC_SECRET not in scrubbed
    assert "[Filtered]" in scrubbed


QUOTED_SECRET = 'alpha"omega-tail'  # noqa: S105  # pragma: allowlist secret


@pytest.mark.parametrize(
    "text",
    [
        json.dumps({"clientSecret": QUOTED_SECRET}),
        repr(json.dumps({"client_secret": QUOTED_SECRET}).encode()),
        repr(repr(json.dumps({"clientSecret": QUOTED_SECRET}))),
        repr({"config": {"clientSecret": QUOTED_SECRET}}),
    ],
)
def test_secret_with_a_quote_is_blanked_whole(text):
    """An escaped quote inside the secret does not end the match early."""
    scrubbed = scrub_secret_values(text)
    assert "omega-tail" not in scrubbed
    assert "[Filtered]" in scrubbed


def test_scrubber_blanks_nested_secret_keys():
    """The request body and nested frame locals, by key, at any depth."""
    event = {
        "request": {"data": {"alias": "partner", "client_secret": OIDC_SECRET}},
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {
                                "vars": {
                                    "data": {
                                        "alias": "partner",
                                        "config": {"clientSecret": OIDC_SECRET},
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        },
    }
    build_event_scrubber(collect_user_info=False).scrub_event(event)
    assert OIDC_SECRET not in repr(event)
    frame_vars = event["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
    assert frame_vars["data"]["alias"] == "partner"


def _init_scrubbing_sdk(*, collect_user_info, **kwargs):
    """Initialize the real SDK with our data_collection and hooks, as init_sentry does."""
    transport = FakeTransport()
    sentry_sdk.init(
        dsn="https://k@o0.ingest.sentry.io/0",
        transport=transport,
        before_send=before_send,
        before_send_transaction=before_send_transaction,
        data_collection=build_data_collection(collect_user_info=collect_user_info),
        default_integrations=False,
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        ],
        **kwargs,
    )
    return transport


@pytest.fixture(params=[True, False], ids=["user_info", "no_user_info"])
def scrubbing_sentry_transport(request):
    """Initialize the real SDK with our scrubbing, with user info on and off."""
    yield _init_scrubbing_sdk(collect_user_info=request.param)
    sentry_sdk.get_global_scope().set_client(None)


def test_real_sdk_keeps_the_oidc_secret_out(scrubbing_sentry_transport):
    """An IdP create that fails in Keycloak must not ship the secret in locals."""

    def create_identity_provider(client_secret):
        config = {"clientId": "partner", "clientSecret": client_secret}
        payload = {"alias": "partner", "config": config}
        body = json.dumps(payload).encode()
        representation = IdentityProviderPayload(alias="partner", config=config)
        msg = "Keycloak said no"
        raise RuntimeError(msg, len(body), representation.alias)

    try:
        create_identity_provider(OIDC_SECRET)
    except RuntimeError:
        logging.getLogger("b2b").exception("Keycloak call failed during provisioning")
    sentry_sdk.flush()

    assert len(scrubbing_sentry_transport.events) == 1
    event_json = json.dumps(scrubbing_sentry_transport.events[0])
    assert OIDC_SECRET not in event_json
    assert "Keycloak said no" in event_json


@pytest.mark.parametrize("collect_user_info", [True, False])
def test_data_collection_matches_send_default_pii(collect_user_info):
    """Resolved by the SDK, it collects exactly what send_default_pii did."""
    resolved = _resolve_explicit(
        build_data_collection(collect_user_info=collect_user_info)
    )
    expected = _map_from_send_default_pii(
        send_default_pii=collect_user_info,
        include_local_variables=True,
        include_source_context=True,
    )
    assert resolved.pop("provided_by_user") is True
    assert expected.pop("provided_by_user") is False
    if not collect_user_info:
        # send_default_pii=False sent no cookies; the SDK's mapping would
        # send them through its denylist instead.
        assert resolved.pop("cookies") == {"mode": "off"}
        expected.pop("cookies")
    assert resolved == expected


@pytest.mark.parametrize("collect_user_info", [True, False])
def test_init_sentry_configures_data_collection(collect_user_info):
    """init_sentry no longer sets the deprecated option, and keeps its hooks.

    pytest turns warnings into errors, so a send_default_pii or ignored
    event_scrubber deprecation warning fails this test.
    """
    try:
        init_sentry(
            dsn="https://k@o0.ingest.sentry.io/0",
            environment="test",
            version="0.0.0",
            collect_user_info=collect_user_info,
            log_level="ERROR",
            heroku_app_name=None,
            traces_sample_rate=0,
            profiles_sample_rate=0,
        )
        options = sentry_sdk.get_client().options
    finally:
        sentry_sdk.get_global_scope().set_client(None)

    assert options["send_default_pii"] is None
    assert options["event_scrubber"] is None
    assert options["data_collection"]["provided_by_user"] is True
    assert options["data_collection"]["user_info"] is collect_user_info
    assert options["max_request_body_size"] == "small"
    assert options["before_send"] is before_send
    assert options["before_send_transaction"] is before_send_transaction


def test_real_sdk_scrubs_ip_keys_only_without_user_info(scrubbing_sentry_transport):
    """The PII denylist follows user_info, as it followed send_default_pii."""
    collect_user_info = sentry_sdk.get_client().options["data_collection"]["user_info"]

    def handle(remote_addr):
        raise RuntimeError(remote_addr)

    try:
        handle("192.0.2.10")
    except RuntimeError as e:
        sentry_sdk.capture_exception(e)
    sentry_sdk.flush()

    (event,) = scrubbing_sentry_transport.events
    frame = event["exception"]["values"][0]["stacktrace"]["frames"][-1]
    assert frame["function"] == "handle"
    if collect_user_info:
        assert frame["vars"]["remote_addr"] == "'192.0.2.10'"
    else:
        assert frame["vars"]["remote_addr"] == "[Filtered]"


def test_real_sdk_scrubs_secret_keys_in_transactions(scrubbing_sentry_transport):
    """The event_scrubber covered span data; before_send_transaction must too."""
    sentry_sdk.get_client().options["traces_sample_rate"] = 1.0
    with sentry_sdk.start_transaction(name="provision"):  # noqa: SIM117
        with sentry_sdk.start_span(op="keycloak") as span:
            span.set_data("client_secret", OIDC_SECRET)
            span.set_data("alias", "partner")
    sentry_sdk.flush()

    (event,) = scrubbing_sentry_transport.events
    assert event["type"] == "transaction"
    event_json = json.dumps(event)
    assert OIDC_SECRET not in event_json
    assert event["spans"][0]["data"]["alias"] == "partner"
    assert event["spans"][0]["data"]["client_secret"] == "[Filtered]"  # noqa: S105


def test_real_sdk_keeps_the_explicit_user(scrubbing_sentry_transport):
    """A user set on the scope reaches before_send whatever user_info says."""
    sentry_sdk.set_user(dict(LEARNER_USER))
    sentry_sdk.capture_message("boom")
    sentry_sdk.flush()

    (event,) = scrubbing_sentry_transport.events
    assert event["user"] == LEARNER_USER


def failing_view(request):
    """Raise inside a request, so DjangoIntegration attaches the request and user."""
    msg = "boom"
    raise RuntimeError(msg)


urlpatterns = [path("sentry-boom/", failing_view), *main_urlpatterns]


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=__name__)
@pytest.mark.parametrize("collect_user_info", [True, False])
def test_django_request_event(client, collect_user_info):
    """The request user and cookies are sent only with user info, as with send_default_pii."""
    user = UserFactory.create()
    transport = FakeTransport()
    sentry_sdk.init(
        dsn="https://k@o0.ingest.sentry.io/0",
        transport=transport,
        before_send=before_send,
        data_collection=build_data_collection(collect_user_info=collect_user_info),
        max_request_body_size="small",
        integrations=[DjangoIntegration()],
    )
    try:
        client.force_login(user)
        client.cookies["tracking"] = "abc"
        with pytest.raises(Exception):  # noqa: B017, PT011
            client.post(
                "/sentry-boom/", data={"name": "Ada", "client_secret": OIDC_SECRET}
            )
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_global_scope().set_client(None)

    (event,) = [
        event
        for event in transport.events
        if event["exception"]["values"][-1]["value"] == "boom"
    ]
    request = event["request"]
    assert request["data"] == {"name": "Ada", "client_secret": "[Filtered]"}
    if collect_user_info:
        assert event["user"]["email"] == user.email
        assert request["cookies"]["tracking"] == "abc"
        assert request["cookies"]["mitxonline_sessionid"] == "[Filtered]"
    else:
        assert "user" not in event
        assert "cookies" not in request


LEARNER_ADDRESS = "77 Massachusetts Ave"


def _exception_event(*modules):
    """Build an event whose stack has one frame per module, each with locals."""
    return {
        "exception": {
            "values": [
                {
                    "value": "400 Bad Request",
                    "stacktrace": {
                        "frames": [
                            {
                                "module": module,
                                "function": "f",
                                "vars": {
                                    "body": f'{{"address1": "{LEARNER_ADDRESS}"}}'
                                },
                            }
                            for module in modules
                        ]
                    },
                }
            ]
        }
    }


@pytest.mark.parametrize(
    "module",
    [
        "compliance.api",
        "CyberSource.api_client",
        "CyberSource.rest",
        "authenticationsdk.core.Authorization",
    ],
)
def test_export_compliance_event_loses_every_frames_locals(module):
    """One compliance or SDK frame strips locals from callers and urllib3 too."""
    event = _exception_event("courses.api", module, "urllib3.connectionpool")
    before_send(event, {})
    frames = event["exception"]["values"][0]["stacktrace"]["frames"]
    assert [frame["module"] for frame in frames] == [
        "courses.api",
        module,
        "urllib3.connectionpool",
    ]
    assert all("vars" not in frame for frame in frames)


@pytest.mark.parametrize("module", ["courses.api", "compliancefoo", "cybersource"])
def test_other_events_keep_their_locals(module):
    """Only the compliance app and the CyberSource SDK trigger the strip."""
    event = _exception_event(module)
    scrub_export_compliance_event(event)
    assert event["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]


@pytest.mark.parametrize("module", ["compliance.exceptions", "CyberSource.rest"])
def test_export_compliance_exception_outside_compliance_frames(module):
    """An ExportComplianceError raised by its caller is caught by its own module."""
    event = _exception_event("courses.api", "courses.views.v1")
    event["exception"]["values"][0]["module"] = module
    before_send(event, {})
    assert LEARNER_ADDRESS not in json.dumps(event)


def test_thread_stacktraces_are_covered():
    """A logged message with attach_stacktrace puts frames under threads."""
    event = {"threads": _exception_event("compliance.api", "main.views")["exception"]}
    scrub_export_compliance_event(event)
    assert LEARNER_ADDRESS not in json.dumps(event)


def test_export_compliance_user_becomes_the_tagged_global_id():
    """The tag compliance.api sets replaces the request user's email and username."""
    event = _exception_event("compliance.api")
    event["user"] = dict(LEARNER_USER)
    event["tags"] = {EXPORT_COMPLIANCE_USER_TAG: "kc-uuid"}
    scrub_export_compliance_event(event)
    assert event["user"] == {"id": "kc-uuid"}


def test_export_compliance_user_without_tag_is_dropped():
    """With no global_id to fall back on, the user is removed rather than kept."""
    event = _exception_event("CyberSource.rest")
    event["user"] = dict(LEARNER_USER)
    scrub_export_compliance_event(event)
    assert "user" not in event


def test_other_events_keep_their_user():
    """Events outside export compliance keep what send_default_pii attached."""
    event = _exception_event("courses.api")
    event["user"] = dict(LEARNER_USER)
    event["tags"] = {EXPORT_COMPLIANCE_USER_TAG: "kc-uuid"}
    scrub_export_compliance_event(event)
    assert event["user"] == LEARNER_USER
