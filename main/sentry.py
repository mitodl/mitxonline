"""Sentry setup and configuration"""

import logging
import re

import sentry_sdk
from celery.exceptions import WorkerLostError
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

# these errors occur when a shutdown is happening (usually caused by a SIGTERM)
SHUTDOWN_ERRORS = (WorkerLostError, SystemExit)

log = logging.getLogger()


# Postgres appends a DETAIL line to constraint violations that echoes the whole
# offending row -- on a users table that is the learner's name, email and
# external UUID.  psycopg puts it in str(exc), so it ships inside the exception
# value, where no SDK privacy setting reaches it: data_collection governs
# user/cookie/header capture and max_request_body_size governs request bodies,
# and neither touches exception text.
#
# The newline is matched both raw and as a literal backslash-n: the SDK repr()s
# frame locals and non-string logging params during serialization, so there the
# DETAIL line arrives as "...constraint\\nDETAIL: ..." inside a repr string.
PG_DETAIL_RE = re.compile(r"(\n|\\n)DETAIL:.*", re.DOTALL)


def scrub_pg_detail(text):
    """Truncate a Postgres error string at its DETAIL line.

    Keeps the primary message, which is what identifies the failure, and drops
    the row echo plus any HINT/CONTEXT Postgres appends after it.
    """
    return PG_DETAIL_RE.sub(
        lambda match: match.group(1) + "DETAIL:  [scrubbed]", text, count=1
    )


# The SDK's EventScrubber matches whole key names, so "client_secret" and
# Keycloak's "clientSecret" (the OIDC IdP config b2b.provisioning sends) pass
# its default denylist, which only has "secret". The request body carries the
# first and captured frame locals the second.
SECRET_KEYS = ["client_secret", "clientsecret"]

# Key matching cannot reach a secret inside a string: requests' frames hold the
# JSON body it sent as bytes, and objects in frame locals arrive repr()d. This
# blanks the value of any client-secret pair in JSON or repr form, including
# one escaped inside another string. The value ends at a quote carrying exactly
# the opening quote's backslashes, so a quote escaped inside the secret itself
# (which carries more) does not end it early.
SECRET_PAIR_RE = re.compile(
    r"(client_?secret\\*['\"]?\s*[:=]\s*)(\\*)(['\"])(.*?)(?<!\\)(\2\3)",
    re.IGNORECASE,
)


def build_event_scrubber(*, collect_user_info):
    """Return the SDK's scrubber, extended with our secret keys and made recursive.

    Recursive because the secret sits nested in frame locals, e.g. the
    identity provider payload's config["clientSecret"]. Without user info the
    SDK's PII denylist (IP address keys) is scrubbed too, as it was when this
    followed send_default_pii.
    """
    return EventScrubber(
        denylist=[*DEFAULT_DENYLIST, *SECRET_KEYS],
        recursive=True,
        send_default_pii=collect_user_info,
    )


def build_data_collection(*, collect_user_info):
    """Return the data_collection option that matches send_default_pii.

    Follows sentry_sdk.data_collection._map_from_send_default_pii, which is
    what the SDK derives from send_default_pii, so moving off the deprecated
    option leaves collection as it was. Header and query-param terms are the
    extra keys send_default_pii=False filtered (proxy and remote address
    headers); the SDK's own sensitive denylist (auth, token, session, csrf,
    ...) applies in denylist mode either way. Request bodies stay on
    regardless: max_request_body_size in init_sentry is what bounds them.

    One departure from that mapping: without user info, cookies are off.
    The mapping sends them through the denylist, but send_default_pii=False
    sent no cookies at all (RequestExtractor.extract_into_event).
    """
    terms = [] if collect_user_info else ["forwarded", "-ip", "remote-", "via", "-user"]
    return {
        "user_info": collect_user_info,
        "cookies": (
            {"mode": "denylist", "terms": terms}
            if collect_user_info
            else {"mode": "off"}
        ),
        "http_headers": {"request": {"mode": "denylist", "terms": terms}},
        "http_bodies": ["incoming_request", "outgoing_request", "outgoing_response"],
        "url_query_params": {"mode": "denylist", "terms": terms},
        "graphql": {"document": collect_user_info, "variables": collect_user_info},
        "gen_ai": {"inputs": collect_user_info, "outputs": collect_user_info},
        "database_query_data": collect_user_info,
        "queues": collect_user_info,
        "stack_frame_variables": True,
        "frame_context_lines": 5,
    }


def scrub_secret_values(text):
    """Blank the value of any client-secret key/value pair inside a string."""
    return SECRET_PAIR_RE.sub(r"\1\2\3[Filtered]\5", text)


def scrub_pg_details(event):
    """Truncate Postgres DETAIL lines everywhere in a Sentry event.

    The row echo reaches Sentry through more fields than the exception value:
    LoggingIntegration puts the log message in a breadcrumb
    (BreadcrumbHandler._breadcrumb_from_record), logger.error("...: %s", exc)
    puts it in logentry.params (EventHandler._emit), and captured stack-frame
    locals carry it in frame vars because include_local_variables defaults to
    True (serialize_frame).  Walking the whole event covers those without
    enumerating them, and does not go stale when the SDK adds another.

    Safe to walk naively because Client._prepare_event serializes the event
    before calling before_send, so every leaf here is already a JSON
    primitive -- no live exception objects to coerce.
    """
    return _scrub_node(event)


def _scrub_node(node):
    """Recurse through the serialized event, rewriting strings in place."""
    if isinstance(node, str):
        return scrub_secret_values(scrub_pg_detail(node))
    if isinstance(node, dict):
        for key, value in node.items():
            node[key] = _scrub_node(value)
        return node
    if isinstance(node, list):
        node[:] = [_scrub_node(item) for item in node]
        return node
    return node


# The export compliance check sends CyberSource the learner's name, address and
# email (compliance.api._build_bill_to), and that payload sits in frame locals
# all the way down the stack: as a dict and a JSON string in compliance.api, as
# the SDK's body param through CyberSource.api_client and its signing code in
# authenticationsdk, and in the callers holding the user and legal address.
# Neither key-name scrubbing nor a value regex can follow it through every one
# of those shapes (MITXONLINE-6ZY, 73F), so an event whose stack passes through
# this code keeps its frames but none of their locals.
EXPORT_COMPLIANCE_MODULES = ("compliance", "CyberSource", "authenticationsdk")

# Collecting user info also puts the request user's email and username on the
# event (DjangoIntegration's _set_user_info). compliance.api tags the scope with
# the checked learner's global_id, which replaces the user on those events.
EXPORT_COMPLIANCE_USER_TAG = "export_compliance_user"


def _iter_stacktrace_frames(event):
    """Yield every stack frame in the event's exceptions and threads."""
    for section in ("exception", "threads"):
        for value in (event.get(section) or {}).get("values") or []:
            yield from (value.get("stacktrace") or {}).get("frames") or []


def _is_export_compliance_module(module):
    """Return True for a module in our compliance app or the CyberSource SDK."""
    module = module or ""
    return any(
        module == name or module.startswith(f"{name}.")
        for name in EXPORT_COMPLIANCE_MODULES
    )


def _is_export_compliance_event(event, frames):
    """Return True when a frame or a raised exception's class is compliance code.

    The exception's own module catches ExportComplianceError, which
    courses.api raises after verify_user_with_exports has returned, so none of
    its frames are in compliance code while its caller still holds the result
    (and the raw CyberSource response) in its locals.
    """
    exceptions = (event.get("exception") or {}).get("values") or []
    return any(
        _is_export_compliance_module(frame.get("module")) for frame in frames
    ) or any(_is_export_compliance_module(value.get("module")) for value in exceptions)


def scrub_export_compliance_event(event):
    """Drop frame locals and user details from an event raised through export compliance code.

    The user is reduced to the learner's global_id when compliance.api tagged
    it, and removed otherwise.
    """
    frames = list(_iter_stacktrace_frames(event))
    if not _is_export_compliance_event(event, frames):
        return event
    for frame in frames:
        frame.pop("vars", None)
    global_id = (event.get("tags") or {}).get(EXPORT_COMPLIANCE_USER_TAG)
    if global_id:
        event["user"] = {"id": global_id}
    else:
        event.pop("user", None)
    return event


def before_send(event, hint):
    """
    Filter or transform events before they're sent to Sentry

    Args:
        event (dict): event object
        hint (dict): event hints, see https://docs.sentry.io/platforms/python/#hints

    Returns:
        dict or None: returns the modified event or None to filter out the event
    """
    if "exc_info" in hint:
        _, exc_value, _ = hint["exc_info"]
        if isinstance(exc_value, SHUTDOWN_ERRORS):
            # so we don't want to report expected shutdown errors to sentry
            return None
    return scrub_pg_details(scrub_export_compliance_event(event))


def init_sentry(  # noqa: PLR0913
    *,
    dsn,
    environment,
    version,
    collect_user_info,
    log_level,
    heroku_app_name,
    traces_sample_rate,
    profiles_sample_rate,
):
    """
    Initializes sentry

    Args:
        dsn (str): the sentry DSN key
        environment (str): the application environment
        version (str): the version of the application
        collect_user_info (bool): enable sending user details (email, username,
            IP address) and other PII-bearing data to associate users to errors
        log_level (str): the sentry log level
        heroku_app_name (str or None): the name of the heroku review app
        traces_sample_rate (int): int between 0 and 100 for the sample rate
        profiles_sample_rate (int): int between 0 and 100 for the sample rate
    """
    if not 0 <= traces_sample_rate <= 1:
        log.error(
            "SENTRY_TRACES_SAMPLE_RATE should be between 0 <= x <= 1, defaulting to 0"
        )
        traces_sample_rate = 0

    if not 0 <= profiles_sample_rate <= 1:
        log.error(
            "SENTRY_PROFILES_SAMPLE_RATE should be between 0 <= x <= 1, defaulting to 0"
        )
        profiles_sample_rate = 0
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=version,
        before_send=before_send,
        data_collection=build_data_collection(collect_user_info=collect_user_info),
        # Request bodies are NOT gated on user info: data_collection's
        # http_bodies keeps them on, and request_body_within_bounds makes this
        # the only size control.  Left unset it defaults to "medium", i.e.
        # 10,000-byte bodies -- enrollment, checkout, profile and SCIM
        # payloads.  Set explicitly so the choice is findable here rather than
        # in a dependency's defaults.
        max_request_body_size="small",
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            LoggingIntegration(level=log_level),
        ],
    )
    # Passing data_collection makes sentry_sdk.client._get_options drop the
    # event_scrubber option, with a warning, so it is set on the client after
    # init instead. _prepare_event reads it per event and runs it before
    # serialization. That ordering matters: the serializer repr()s anything
    # nested past MAX_DATABAG_DEPTH, and no key-based scrub in before_send can
    # see into that string.
    sentry_sdk.get_client().options["event_scrubber"] = build_event_scrubber(
        collect_user_info=collect_user_info
    )

    with sentry_sdk.configure_scope() as scope:
        if heroku_app_name:
            scope.set_tag("review_app_name", heroku_app_name)
