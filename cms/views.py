import logging

from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from mitol.olposthog.features import is_enabled
from rest_framework.decorators import api_view
from rest_framework.response import Response
from wagtail.models import Page
from wagtail.users.views.users import UserViewSet as WagtailUserViewSet

from cms.credential_metadata import (
    CredentialMetadataUnavailableError,
    fetch_credential_metadata,
)
from cms.models import CoursePage, InstructorPage, ProgramPage
from cms.serializers import InstructorPageSerializer
from main import features

log = logging.getLogger(__name__)


@api_view(["GET"])
def instructor_page(request, pk, format=None):  # noqa: A002, ARG001
    page = InstructorPage.objects.get(pk=pk)

    return Response(InstructorPageSerializer(page).data)


class WagtailUsersViewSet(WagtailUserViewSet):
    """Extends Wagtail's User viewset to work with our custom User model."""

    ordering = "email"


@require_GET
def credential_metadata(request, parent_page_id):
    """
    Return MIT Learn's draft credential text for a course or program page.

    Backs the "Generate with AI" buttons on CertificatePage, so it is keyed on
    the certificate's parent page: that page exists even while the certificate
    itself is still being created.
    """
    # The flag hides the buttons, but also refuse here, so that turning it off
    # switches the feature off entirely rather than only hiding it.
    if not is_enabled(features.ENABLE_CREDENTIAL_METADATA_AUTHORING):
        raise Http404

    parent = get_object_or_404(Page, id=parent_page_id).specific
    if not isinstance(parent, (CoursePage, ProgramPage)):
        raise Http404

    permissions = parent.permissions_for_user(request.user)
    if not (permissions.can_edit() or permissions.can_add_subpage()):
        # Returned, not raised: Wagtail's admin wrapper turns PermissionDenied
        # into a redirect to the dashboard unless the request is flagged XHR.
        return HttpResponseForbidden()

    readable_id = parent.product.readable_id
    try:
        metadata = fetch_credential_metadata(readable_id)
    except CredentialMetadataUnavailableError:
        log.warning(
            "Credential metadata unavailable for %s", readable_id, exc_info=True
        )
        return JsonResponse({"status": "unavailable"}, status=503)

    if metadata is None:
        return JsonResponse({"status": "empty"})

    return JsonResponse(
        {
            "status": "ok",
            "description": metadata.description,
            "criteria": metadata.criteria,
            "errors": metadata.errors,
        }
    )
