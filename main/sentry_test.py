"""Tests for Sentry event scrubbing."""

import json
import logging
import re
from dataclasses import dataclass
from functools import partial

import pytest
import sentry_sdk
from django.core.exceptions import MiddlewareNotUsed
from django.core.handlers.wsgi import WSGIHandler
from django.http import HttpResponseServerError
from django.test import RequestFactory
from django.urls import path
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.transport import Transport

from main.sentry import (
    EXPORT_COMPLIANCE_USER_TAG,
    SentryUserHashMiddleware,
    apply_hashed_user,
    before_send,
    before_send_transaction,
    build_event_scrubber,
    hash_user_id,
    scrub_export_compliance_event,
    scrub_pg_detail,
    scrub_pg_details,
    scrub_secret_values,
)

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
            item.payload.json for item in envelope.items if item.type == "event"
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
    build_event_scrubber(send_default_pii=False).scrub_event(event)
    assert OIDC_SECRET not in repr(event)
    frame_vars = event["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
    assert frame_vars["data"]["alias"] == "partner"


@pytest.fixture
def scrubbing_sentry_transport():
    """Initialize the real SDK with our scrubber as well as before_send."""
    transport = FakeTransport()
    sentry_sdk.init(
        dsn="https://k@o0.ingest.sentry.io/0",
        transport=transport,
        before_send=before_send,
        event_scrubber=build_event_scrubber(send_default_pii=False),
        default_integrations=False,
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        ],
    )
    yield transport
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


LEARNER_USER = {"id": "42", "email": "learner@example.invalid", "username": "ada"}


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


HASH_KEY = b"test-hash-key"


@dataclass
class FakeUser:
    """The two attributes apply_hashed_user reads."""

    pk: int
    is_authenticated: bool = True


@dataclass
class FakeRequest:
    """A request carrying only a user."""

    user: object


class RaisingRequest:
    """A request whose lazy user fails to load, as when the database is down."""

    @property
    def user(self):
        """Raise the way SimpleLazyObject does when the auth lookup fails."""
        msg = "database unavailable"
        raise RuntimeError(msg)


def _serve(request, func):
    """Run func inside SentryUserHashMiddleware for request."""
    return SentryUserHashMiddleware(lambda _request: func())(request)


def test_hash_is_keyed_and_truncated():
    """The id is a 16-hex HMAC that changes with the key and with the user."""
    digest = hash_user_id(HASH_KEY, 42)
    assert re.fullmatch(r"[0-9a-f]{16}", digest)
    assert digest == hash_user_id(HASH_KEY, 42)
    assert digest != hash_user_id(b"another-key", 42)
    assert digest != hash_user_id(HASH_KEY, 43)


@pytest.mark.parametrize(
    ("request_", "expected"),
    [
        (FakeRequest(FakeUser(42)), {"id": hash_user_id(HASH_KEY, 42)}),
        (FakeRequest(FakeUser(42, is_authenticated=False)), None),
        (RaisingRequest(), None),
    ],
)
def test_user_is_replaced_by_the_hash_or_dropped(settings, request_, expected):
    """Whatever the SDK attached is gone; only the hash of an authenticated user remains."""
    settings.SENTRY_USER_HASH_KEY = HASH_KEY.decode()
    event = {"user": dict(LEARNER_USER, ip_address="192.0.2.1")}
    _serve(request_, lambda: apply_hashed_user(event, HASH_KEY))
    assert event.get("user") == expected


def test_event_outside_a_request_carries_no_user():
    """A Celery task or an outer middleware has no request, so no user at all."""
    event = {"user": dict(LEARNER_USER)}
    apply_hashed_user(event, HASH_KEY)
    assert "user" not in event


def test_middleware_opts_out_without_a_key(settings):
    """No key, no middleware: Django drops it from the chain."""
    settings.SENTRY_USER_HASH_KEY = ""
    with pytest.raises(MiddlewareNotUsed):
        SentryUserHashMiddleware(lambda _request: None)


def test_middleware_releases_the_request(settings):
    """The request is not left behind for the next event on this thread."""
    settings.SENTRY_USER_HASH_KEY = HASH_KEY.decode()
    _serve(FakeRequest(FakeUser(42)), lambda: None)
    event = {}
    apply_hashed_user(event, HASH_KEY)
    assert "user" not in event


def test_export_compliance_global_id_wins_over_the_hash(settings):
    """A compliance event names the checked learner, who may not be the requester."""
    settings.SENTRY_USER_HASH_KEY = HASH_KEY.decode()
    event = _exception_event("compliance.api")
    event["tags"] = {EXPORT_COMPLIANCE_USER_TAG: "kc-uuid"}
    _serve(
        FakeRequest(FakeUser(42)),
        lambda: before_send(event, {}, user_hash_key=HASH_KEY),
    )
    assert event["user"] == {"id": "kc-uuid"}


def test_transactions_carry_no_user():
    """A transaction finishes after the middleware, so its user is dropped."""
    event = {"type": "transaction", "user": dict(LEARNER_USER)}
    assert "user" not in before_send_transaction(event, {})


def test_real_sdk_sends_only_the_hash(settings):
    """Through the real SDK, even with send_default_pii on, the event's user is the hash."""
    settings.SENTRY_USER_HASH_KEY = HASH_KEY.decode()
    transport = FakeTransport()
    sentry_sdk.init(
        dsn="https://k@o0.ingest.sentry.io/0",
        transport=transport,
        before_send=partial(before_send, user_hash_key=HASH_KEY),
        send_default_pii=True,
        default_integrations=False,
    )
    try:
        with sentry_sdk.new_scope() as scope:
            scope.set_user(dict(LEARNER_USER, ip_address="192.0.2.1"))
            _serve(
                FakeRequest(FakeUser(42)),
                lambda: sentry_sdk.capture_message("boom"),
            )
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_global_scope().set_client(None)
    assert [event["user"] for event in transport.events] == [
        {"id": hash_user_id(HASH_KEY, 42)}
    ]


def test_other_events_lose_the_export_compliance_tag():
    """A later error in the same request must not tie the hash to a global_id."""
    event = _exception_event("courses.api")
    event["tags"] = {EXPORT_COMPLIANCE_USER_TAG: "kc-uuid", "other": "kept"}
    scrub_export_compliance_event(event)
    assert event["tags"] == {"other": "kept"}


APISIX_IDENTITY_HEADERS = {
    "X-Userinfo": "eyJlbWFpbCI6ICJsZWFybmVyQGV4YW1wbGUuaW52YWxpZCJ9",
    "X-Id-Token": "id.token.value",
    "X-Access-Token": "access.token.value",
    "X-Refresh-Token": "refresh.token.value",
}


def test_scrubber_blanks_apisix_identity_headers():
    """The headers APISIX authenticates the user with are blanked; others stay."""
    event = {"request": {"headers": {**APISIX_IDENTITY_HEADERS, "Accept": "*/*"}}}
    build_event_scrubber(send_default_pii=False).scrub_event(event)
    headers = event["request"]["headers"]
    assert headers["Accept"] == "*/*"
    assert not set(APISIX_IDENTITY_HEADERS.values()) & {
        value for value in headers.values() if isinstance(value, str)
    }


def _raising_view(request):
    """Stand in for an authenticated view that fails."""
    request.user = FakeUser(42)
    msg = "boom"
    raise RuntimeError(msg)


def _server_error(_request):
    """Skip the site's 500 template, which needs a full request context."""
    return HttpResponseServerError()


urlpatterns = [path("boom/", _raising_view)]
handler500 = _server_error


def test_real_django_request_sends_only_the_hash(settings):
    """Through the WSGI handler DjangoIntegration wraps: hashed user, no identity headers."""
    settings.SENTRY_USER_HASH_KEY = HASH_KEY.decode()
    settings.MIDDLEWARE = ["main.sentry.SentryUserHashMiddleware"]
    settings.ROOT_URLCONF = __name__
    transport = FakeTransport()
    sentry_sdk.init(
        dsn="https://k@o0.ingest.sentry.io/0",
        transport=transport,
        before_send=partial(before_send, user_hash_key=HASH_KEY),
        event_scrubber=build_event_scrubber(send_default_pii=False),
        send_default_pii=False,
        default_integrations=False,
        integrations=[DjangoIntegration()],
    )
    try:
        headers = {
            f"HTTP_{name.upper().replace('-', '_')}": value
            for name, value in APISIX_IDENTITY_HEADERS.items()
        }
        environ = RequestFactory()._base_environ(PATH_INFO="/boom/", **headers)  # noqa: SLF001
        WSGIHandler()(environ, lambda _status, _headers: None)
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_global_scope().set_client(None)
    [event] = transport.events
    assert event["user"] == {"id": hash_user_id(HASH_KEY, 42)}
    assert not set(APISIX_IDENTITY_HEADERS.values()) & set(
        map(str, event["request"]["headers"].values())
    )


def test_export_compliance_log_event_keeps_the_global_id():
    """compliance.api's log.error has no frames; its logger name marks it."""
    event = {
        "logger": "compliance.api",
        "user": {"id": "hashed"},
        "tags": {EXPORT_COMPLIANCE_USER_TAG: "kc-uuid"},
    }
    scrub_export_compliance_event(event)
    assert event["user"] == {"id": "kc-uuid"}
    assert event["tags"] == {EXPORT_COMPLIANCE_USER_TAG: "kc-uuid"}
