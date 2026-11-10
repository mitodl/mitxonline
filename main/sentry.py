"""Sentry setup and configuration"""

import hashlib
import hmac
import logging
import re
from contextvars import ContextVar
from functools import partial

import sentry_sdk
from celery.exceptions import WorkerLostError
from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed
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
# value, where no SDK privacy setting reaches it: send_default_pii governs
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

# APISIX's openid-connect plugin hands the app the logged-in user as request
# headers: X-Userinfo is base64 JSON with their email and name, the others are
# their tokens.  With send_default_pii off the SDK still sends every header
# except Cookie, Authorization, X-Api-Key and the two forwarded-for headers
# (_wsgi_common._filter_headers), so these go on the denylist.  The scrubber
# lowercases header names before matching.
IDENTITY_HEADER_KEYS = [
    "x-userinfo",
    "x-id-token",
    "x-access-token",
    "x-refresh-token",
    "x-raw-id-token",
]

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


def build_event_scrubber(*, send_default_pii):
    """Return the SDK's scrubber, extended with our secret keys and made recursive.

    Recursive because the secret sits nested in frame locals, e.g. the
    identity provider payload's config["clientSecret"].
    """
    return EventScrubber(
        denylist=[*DEFAULT_DENYLIST, *SECRET_KEYS, *IDENTITY_HEADER_KEYS],
        recursive=True,
        send_default_pii=send_default_pii,
    )


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

# send_default_pii also puts the request user's email and username on the
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
    (and the raw CyberSource response) in its locals.  A log.error from
    compliance code carries no frames at all, so its logger name counts too.
    """
    exceptions = (event.get("exception") or {}).get("values") or []
    return (
        _is_export_compliance_module(event.get("logger"))
        or any(_is_export_compliance_module(frame.get("module")) for frame in frames)
        or any(
            _is_export_compliance_module(value.get("module")) for value in exceptions
        )
    )


def scrub_export_compliance_event(event):
    """Drop frame locals and user details from an event raised through export compliance code.

    The user is reduced to the learner's global_id when compliance.api tagged
    it, and removed otherwise.
    """
    frames = list(_iter_stacktrace_frames(event))
    if not _is_export_compliance_event(event, frames):
        # set_tag lasts the whole request, so a later unrelated error would
        # carry the learner's global_id next to their hashed user id and tie
        # the two together for good.
        (event.get("tags") or {}).pop(EXPORT_COMPLIANCE_USER_TAG, None)
        return event
    for frame in frames:
        frame.pop("vars", None)
    global_id = (event.get("tags") or {}).get(EXPORT_COMPLIANCE_USER_TAG)
    if global_id:
        event["user"] = {"id": global_id}
    else:
        event.pop("user", None)
    return event


# With send_default_pii off the SDK attaches no user, so Sentry cannot count
# the users an issue affects.  SENTRY_USER_HASH_KEY restores the count without
# the identity: user.id becomes an HMAC of the user's primary key and nothing
# else about the user is sent.  The key is the whole privacy property, because
# primary keys are small sequential integers and an unkeyed hash of one is
# reversed by enumeration.  Rotating it makes every user look new.
#
# The write happens in before_send, the last hook to touch an event.  An event
# processor would run before the SDK's Django user processor, which (if
# send_default_pii were turned back on) would add email and username next to
# the hash.
USER_HASH_HEX_LENGTH = 16

_current_request = ContextVar("mitxonline_sentry_current_request", default=None)


def hash_user_id(key, user_pk):
    """Return the keyed, truncated digest that stands in for a user id."""
    digest = hmac.new(key, str(user_pk).encode(), hashlib.sha256).hexdigest()
    return digest[:USER_HASH_HEX_LENGTH]


def apply_hashed_user(event, key):
    """Replace the event's user with the hashed id of the requesting user.

    The user is dropped before request.user is read: that attribute is lazy and
    can raise (the database may be what failed), and an event sent outside a
    request (a Celery task, an outer middleware) must carry no user rather than
    whatever the SDK attached.  The user is read at send time because DRF
    authenticates token requests inside the view.
    """
    event.pop("user", None)
    try:
        user = getattr(_current_request.get(), "user", None)
        if user is not None and user.is_authenticated:
            event["user"] = {"id": hash_user_id(key, user.pk)}
    except Exception:  # noqa: BLE001
        log.warning("Could not read the user to hash for Sentry", exc_info=True)
    return event


class SentryUserHashMiddleware:
    """Expose the request being served to apply_hashed_user."""

    def __init__(self, get_response):
        """Opt out of the middleware chain when no hash key is configured."""
        if not settings.SENTRY_USER_HASH_KEY:
            raise MiddlewareNotUsed
        self.get_response = get_response

    def __call__(self, request):
        """Record the request for the duration of the inner handlers."""
        token = _current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            _current_request.reset(token)


def before_send(event, hint, *, user_hash_key=None):
    """
    Filter or transform events before they're sent to Sentry

    Args:
        event (dict): event object
        hint (dict): event hints, see https://docs.sentry.io/platforms/python/#hints
        user_hash_key (bytes or None): HMAC key for the hashed user id, or None
            to leave the event's user alone

    Returns:
        dict or None: returns the modified event or None to filter out the event
    """
    if "exc_info" in hint:
        _, exc_value, _ = hint["exc_info"]
        if isinstance(exc_value, SHUTDOWN_ERRORS):
            # so we don't want to report expected shutdown errors to sentry
            return None
    if user_hash_key:
        apply_hashed_user(event, user_hash_key)
    # After the hash, so an export compliance event keeps the checked learner's
    # global_id (which may not be the requesting user) or loses its user.
    return scrub_pg_details(scrub_export_compliance_event(event))


def before_send_transaction(event, _hint):
    """Keep users off transactions.

    The SDK finishes a request's transaction after the middleware has returned,
    so there is no request to hash a user from.
    """
    event.pop("user", None)
    return event


def init_sentry(  # noqa: PLR0913
    *,
    dsn,
    environment,
    version,
    send_default_pii,
    user_hash_key,
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
        send_default_pii (bool): enable sending PII data to associate users to errors
        user_hash_key (str): HMAC key for the hashed user id; empty sends no user
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
        before_send=partial(
            before_send, user_hash_key=user_hash_key.encode() if user_hash_key else None
        ),
        before_send_transaction=before_send_transaction,
        # Request bodies are NOT gated on send_default_pii: the SDK sets
        # request.data unconditionally (RequestExtractor.extract_into_event)
        # and this is the only control (request_body_within_bounds).  Left
        # unset it defaults to "medium", i.e. 10,000-byte bodies -- enrollment,
        # checkout, profile and SCIM payloads.  Set explicitly so the choice is
        # findable here rather than in a dependency's defaults.
        max_request_body_size="small",
        event_scrubber=build_event_scrubber(send_default_pii=send_default_pii),
        send_default_pii=send_default_pii,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            LoggingIntegration(level=log_level),
        ],
    )

    with sentry_sdk.configure_scope() as scope:
        if heroku_app_name:
            scope.set_tag("review_app_name", heroku_app_name)
