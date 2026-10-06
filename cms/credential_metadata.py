"""
Client for MIT Learn's credential metadata API.

MIT Learn generates draft `description` and `criteria` text for MITx Online
courses on a nightly schedule and stores the result. This module reads that
stored text so CMS authors can review and edit it before it is saved to a
certificate page and signed into learners' credentials.

Reads only. Regenerating (the API's POST) spends a frontier-model call and
mutates state shared with MIT Learn, so it is deliberately out of scope here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests
from django.conf import settings

log = logging.getLogger(__name__)

CREDENTIAL_METADATA_PATH = "/api/v0/credential_metadata/"

# The stored text is pre-generated, so this is a cheap read. The timeout only
# needs to cover a slow network, not a model call.
REQUEST_TIMEOUT_SECONDS = 10

HTTP_NOT_FOUND = 404


class CredentialMetadataUnavailableError(Exception):
    """
    MIT Learn could not be reached, or answered with something unusable.

    Distinct from "nothing is stored for this course", which is an ordinary
    outcome and is reported by returning None. This means we could not find
    out, so the caller should offer a retry rather than report an empty draft.
    """


@dataclass
class CredentialMetadata:
    """Draft credential text stored by MIT Learn for one course."""

    readable_id: str
    description: str | None = None
    criteria: str | None = None
    errors: dict[str, str] = field(default_factory=dict)


def is_configured() -> bool:
    """
    Return whether a MIT Learn API host has been configured.

    The setting defaults to empty, so a deployment that has not opted in makes
    no outbound requests. Callers use this to hide the feature rather than
    offer a control that cannot work.
    """
    return bool(settings.MIT_LEARN_API_BASE_URL)


def render_criteria_markdown(criteria: list[str] | None) -> str | None:
    """
    Render MIT Learn's list of criteria bullets as markdown.

    MIT Learn returns criteria as a list of strings; the CMS field stores a
    single markdown blob, so the two have to be reconciled somewhere.

    Args:
        criteria: bullet strings from the API, or None if it did not generate.

    Returns:
        A markdown bulleted list, or None if there were no usable bullets.
    """
    if not criteria:
        return None

    lines = []
    for item in criteria:
        text = str(item).strip()
        if not text:
            continue
        # Don't double up the bullet if the model already wrote one.
        lines.append(text if text.startswith(("- ", "* ")) else f"- {text}")

    return "\n".join(lines) or None


def fetch_credential_metadata(readable_id: str) -> CredentialMetadata | None:
    """
    Fetch the draft credential text MIT Learn has stored for a course.

    Args:
        readable_id: the course's readable id, e.g. "course-v1:MITxT+2.25.1x".

    Returns:
        The stored metadata, or None if no host is configured or MIT Learn has
        nothing stored for this course. Either field may be None on its own:
        MIT Learn omits a field it failed to generate and explains why in
        `errors`, so partial results are normal rather than a failure.

    Raises:
        CredentialMetadataUnavailableError: MIT Learn could not be reached, or
            returned an error status or a body that was not JSON.
    """
    if not is_configured():
        log.debug(
            "MIT_LEARN_API_BASE_URL is not set; skipping credential metadata lookup"
        )
        return None

    base_url = settings.MIT_LEARN_API_BASE_URL.rstrip("/")
    url = f"{base_url}{CREDENTIAL_METADATA_PATH}"

    try:
        response = requests.get(
            url,
            params={"resource_readable_id": readable_id},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        msg = f"Could not reach MIT Learn for {readable_id}"
        raise CredentialMetadataUnavailableError(msg) from exc

    # Nothing stored for this course. A genuine gap rather than an error --
    # note that an unpublished course may still have stored metadata, so this
    # is not a proxy for "course is not published".
    if response.status_code == HTTP_NOT_FOUND:
        log.info("MIT Learn has no stored credential metadata for %s", readable_id)
        return None

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        msg = f"MIT Learn returned {response.status_code} for {readable_id}"
        raise CredentialMetadataUnavailableError(msg) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        # A partially deployed MIT Learn can answer 200 with an HTML error page.
        msg = f"MIT Learn returned a non-JSON response for {readable_id}"
        raise CredentialMetadataUnavailableError(msg) from exc

    if not isinstance(payload, dict):
        msg = f"MIT Learn returned an unexpected payload for {readable_id}"
        raise CredentialMetadataUnavailableError(msg)

    errors = payload.get("errors") or {}

    return CredentialMetadata(
        readable_id=payload.get("resource_readable_id") or readable_id,
        description=payload.get("description") or None,
        criteria=render_criteria_markdown(payload.get("criteria")),
        errors=errors if isinstance(errors, dict) else {},
    )
