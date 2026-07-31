"""Service-to-service B2B views.

TEMPORARY -- delete this module when org-manager status becomes visible in
Keycloak (mitodl/hq#10594).

Unlike everything in manager.py, these endpoints answer questions *about* a
named user rather than about the caller. They exist because `is_manager`
(b2b.models.UserOrganization) is curated only here, in the Django admin, and
never reaches the Keycloak token -- so a downstream service that needs the
flag has no way to learn it except by asking MITx Online.

The one consumer today is ol-analytics-api, which gates its B2B analytics
endpoints on org-manager status. It cannot reuse
ManagerOrganizationViewSet: that viewset scopes its queryset to
`self.request.user`, so a service-authenticated call would always answer
"manages nothing". Nor can it forward the end user's identity -- the APISIX
openid-connect plugin strips client-supplied X-Userinfo/X-Access-Token
headers before they reach an upstream, by design, so a forwarded identity
never survives the gateway.

Hence a service credential plus an explicit subject parameter. Kept in its
own module, off the user-facing manager surface, so that the deletion in
mitodl/hq#10594 is a file removal rather than an unpicking of a live
authorization path.
"""

import uuid

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from oauth2_provider.contrib.rest_framework import OAuth2Authentication, TokenHasScope
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from b2b.models import OrganizationPage, is_organization_manager
from b2b.serializers.v0.service import OrganizationManagerCheckSerializer
from users.models import User

# Distinct from the user-facing scopes in OAUTH2_PROVIDER["SCOPES"]: this one
# is only ever granted to a service Application, never to a user-facing client.
MANAGER_CHECK_SCOPE = "b2b:manager-check"


class OrganizationManagerCheckView(APIView):
    """Answer whether a given user manages a given organization.

    Deliberately fails closed: an unknown user, an unknown organization, or a
    user with no membership row all return `is_manager: false` rather than a
    404. A 404 would let a caller enumerate which Keycloak organization UUIDs
    and user IDs exist here, which is more than this endpoint needs to reveal
    to answer its one question.
    """

    authentication_classes = [OAuth2Authentication]
    permission_classes = [TokenHasScope]
    required_scopes = [MANAGER_CHECK_SCOPE]

    @extend_schema(
        operation_id="b2b_service_organization_manager_check",
        description=(
            "Check whether a user is a manager of an organization. "
            "Service-to-service only; requires the "
            f"`{MANAGER_CHECK_SCOPE}` scope."
        ),
        parameters=[
            OpenApiParameter(
                name="sso_organization_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
                description=(
                    "The organization's Keycloak UUID "
                    "(OrganizationPage.sso_organization_id)."
                ),
            ),
            OpenApiParameter(
                name="user_global_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description="The user's Keycloak subject (User.global_id).",
            ),
        ],
        responses=OrganizationManagerCheckSerializer,
    )
    def get(self, request, *args, **kwargs):  # noqa: ARG002
        """Return the manager status for the (user, organization) pair."""

        sso_organization_id = request.query_params.get("sso_organization_id")
        user_global_id = request.query_params.get("user_global_id")

        missing = [
            name
            for name, value in (
                ("sso_organization_id", sso_organization_id),
                ("user_global_id", user_global_id),
            )
            if not value
        ]
        if missing:
            return Response(
                {
                    "detail": f"Missing required query parameter(s): {', '.join(missing)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # sso_organization_id maps to a UUIDField. Rejecting a malformed value
        # here keeps a bad request a 400 rather than letting the ORM raise on
        # the lookup and turn it into a 500.
        try:
            uuid.UUID(sso_organization_id)
        except ValueError:
            return Response(
                {"detail": "sso_organization_id must be a UUID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = OrganizationPage.objects.filter(
            sso_organization_id=sso_organization_id
        ).first()
        user = User.objects.filter(global_id=user_global_id).first()

        is_manager = bool(
            organization and user and is_organization_manager(user, organization.id)
        )

        return Response(
            OrganizationManagerCheckSerializer({"is_manager": is_manager}).data,
            status=status.HTTP_200_OK,
        )
