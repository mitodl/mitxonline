"""
Staff-only B2B provisioning API (v0).

The runtime replacement for onboarding a customer by opening a Pulumi PR
against ol-infrastructure's olapps.py, and for waiting up to
KEYCLOAK_ORG_SYNC_FREQUENCY seconds for the organization to appear in MITx
Online. See docs/source/b2b/provisioning_api.md.

Everything here is staff-write via IsAdminOrReadOnly. b2b.permissions'
IsOrganizationManager is deliberately not used: an org manager is a
customer-side role and must not be able to provision. The partner-facing
wizard (C2) gets its own permission class scoped by invite token.
"""

import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from requests.exceptions import HTTPError
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin

from b2b.exceptions import (
    AliasCollisionError,
    InvalidLifecycleTransitionError,
    OrphanedKeycloakOrganizationError,
)
from b2b.models import (
    OrganizationIdentityProvider,
    OrganizationOnboarding,
    OrganizationPage,
)
from b2b.provisioning import (
    KeycloakConnection,
    create_identity_provider,
    create_organization,
    delete_identity_provider,
    parse_identity_provider_metadata,
    refresh_identity_provider_metadata,
    transition_identity_provider,
    update_organization,
)
from b2b.serializers.v0.provisioning import (
    CreateIdentityProviderSerializer,
    CreateOrganizationSerializer,
    IdentityProviderTransitionSerializer,
    OrganizationIdentityProviderSerializer,
    OrganizationOnboardingSerializer,
    ParseMetadataSerializer,
    ProvisionedOrganizationSerializer,
    SetOnboardingStateSerializer,
    UpdateOrganizationSerializer,
)
from main.permissions import IsAdminOrReadOnly

log = logging.getLogger(__name__)

DetailSerializer = inline_serializer(
    name="ProvisioningDetailSerializer",
    fields={"detail": serializers.CharField()},
)


class ProvisioningExceptionMixin:
    """
    Turn the provisioning failure modes into the responses the spec calls for.

    A Keycloak call that fails becomes a 502 rather than a 500: our records are
    intact and the operator's next move is to retry, not to open a ticket
    against MITx Online.
    """

    def handle_exception(self, exc):
        """Map provisioning exceptions onto HTTP responses."""

        if isinstance(exc, AliasCollisionError):
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        if isinstance(exc, InvalidLifecycleTransitionError):
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if isinstance(exc, OrphanedKeycloakOrganizationError):
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if isinstance(exc, HTTPError):
            log.exception("Keycloak call failed during provisioning")
            return Response(
                {"detail": "The Keycloak admin API call failed."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return super().handle_exception(exc)


class OrganizationProvisioningViewSet(
    ProvisioningExceptionMixin,
    viewsets.GenericViewSet,
):
    """Provision and inspect B2B organizations."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = ProvisionedOrganizationSerializer
    lookup_field = "org_key"
    lookup_url_kwarg = "org_key"
    queryset = OrganizationPage.objects.select_related("onboarding").prefetch_related(
        "identity_providers"
    )

    def _with_keycloak(self, organization, connection=None):
        """
        Attach the organization's live Keycloak representation to the instance.

        Domains and the post-login redirect live only in Keycloak, so a
        response that did not read them back would be reporting what we asked
        for rather than what is there.
        """

        if organization.sso_organization_id:
            connection = connection or KeycloakConnection()
            organization.keycloak_organization = connection.organizations.get(
                organization.sso_organization_id
            )

        return organization

    @extend_schema(
        request=CreateOrganizationSerializer,
        responses={
            201: ProvisionedOrganizationSerializer,
            409: DetailSerializer,
            502: DetailSerializer,
        },
    )
    def create(self, request):
        """
        Provision a new organization.

        Writes the Keycloak organization first, then the OrganizationPage and
        its onboarding record in one transaction, compensating by deleting the
        Keycloak organization if that transaction fails.
        """

        request_serializer = CreateOrganizationSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        connection = KeycloakConnection()
        organization = create_organization(
            connection=connection, **request_serializer.validated_data
        )

        return Response(
            self.get_serializer(self._with_keycloak(organization, connection)).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={200: ProvisionedOrganizationSerializer, 502: DetailSerializer}
    )
    def retrieve(self, request, org_key=None):  # noqa: ARG002
        """Return an organization, including what Keycloak currently holds."""

        organization = self.get_object()

        return Response(self.get_serializer(self._with_keycloak(organization)).data)

    @extend_schema(
        request=UpdateOrganizationSerializer,
        responses={
            200: ProvisionedOrganizationSerializer,
            400: DetailSerializer,
            502: DetailSerializer,
        },
    )
    def partial_update(self, request, org_key=None):  # noqa: ARG002
        """Update an organization in both systems. org_key cannot change."""

        organization = self.get_object()

        request_serializer = UpdateOrganizationSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        connection = KeycloakConnection()
        organization = update_organization(
            organization, connection=connection, **request_serializer.validated_data
        )

        return Response(
            self.get_serializer(self._with_keycloak(organization, connection)).data
        )

    @extend_schema(
        request=SetOnboardingStateSerializer,
        responses={200: OrganizationOnboardingSerializer},
    )
    @action(detail=True, methods=["post"])
    def onboarding(self, request, org_key=None):  # noqa: ARG002
        """
        Record where this organization is in the onboarding sequence.

        Descriptive only. Nothing in this API gates on the state; it exists so
        a human can answer "what is left for this customer" without reading
        four systems.
        """

        organization = self.get_object()

        request_serializer = SetOnboardingStateSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        onboarding, _ = OrganizationOnboarding.objects.get_or_create(
            organization=organization
        )
        onboarding.set_state(
            request_serializer.validated_data["state"],
            notes=request_serializer.validated_data.get("notes"),
        )

        return Response(OrganizationOnboardingSerializer(onboarding).data)


@extend_schema(
    parameters=[
        # The nested router names the parent lookup after the ORM path it
        # filters on, which is not a field on OrganizationIdentityProvider, so
        # spectacular cannot infer its type.
        OpenApiParameter(
            name="parent_lookup_organization__org_key",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            description="The organization's org key.",
        )
    ]
)
class IdentityProviderProvisioningViewSet(
    ProvisioningExceptionMixin,
    NestedViewSetMixin,
    viewsets.GenericViewSet,
):
    """Provision and manage an organization's identity providers."""

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = OrganizationIdentityProviderSerializer
    lookup_field = "alias"
    lookup_url_kwarg = "alias"
    queryset = OrganizationIdentityProvider.objects.select_related("organization")

    def _organization(self):
        """Return the organization this route is nested under."""

        return get_object_or_404(
            OrganizationPage,
            org_key=self.kwargs["parent_lookup_organization__org_key"],
        )

    @extend_schema(responses={200: OrganizationIdentityProviderSerializer(many=True)})
    def list(self, request, **kwargs):  # noqa: ARG002
        """List the organization's identity providers."""

        return Response(self.get_serializer(self.get_queryset(), many=True).data)

    @extend_schema(responses={200: OrganizationIdentityProviderSerializer})
    def retrieve(self, request, alias=None, **kwargs):  # noqa: ARG002
        """Return a single identity provider."""

        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(
        request=CreateIdentityProviderSerializer,
        responses={
            201: OrganizationIdentityProviderSerializer,
            409: DetailSerializer,
            502: DetailSerializer,
        },
    )
    def create(self, request, **kwargs):  # noqa: ARG002
        """
        Provision an identity provider and link it to the organization.

        The IdP lands in `draft`, which is disabled in Keycloak. Nobody can
        reach it until it is transitioned to `testing`.
        """

        request_serializer = CreateIdentityProviderSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        payload = dict(request_serializer.validated_data)
        payload.pop("discovery_url", None)

        identity_provider = create_identity_provider(self._organization(), **payload)

        return Response(
            self.get_serializer(identity_provider).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(responses={204: None, 502: DetailSerializer})
    def destroy(self, request, alias=None, **kwargs):  # noqa: ARG002
        """Unlink and delete an identity provider."""

        delete_identity_provider(self.get_object())

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=None,
        responses={
            200: OrganizationIdentityProviderSerializer,
            502: DetailSerializer,
        },
    )
    @action(detail=True, methods=["post"], url_path="refresh-metadata")
    def refresh_metadata(self, request, alias=None, **kwargs):  # noqa: ARG002
        """
        Re-fetch the partner's metadata and store what came back.

        On failure the stored artifact is left untouched, which is the whole
        reason it is stored.
        """

        return Response(
            self.get_serializer(
                refresh_identity_provider_metadata(self.get_object())
            ).data
        )

    @extend_schema(
        request=IdentityProviderTransitionSerializer,
        responses={
            200: OrganizationIdentityProviderSerializer,
            400: DetailSerializer,
            502: DetailSerializer,
        },
    )
    @action(detail=True, methods=["post"])
    def transition(self, request, alias=None, **kwargs):  # noqa: ARG002
        """
        Move the identity provider's lifecycle state.

        The only mover, and it writes Keycloak's enabled flag in the same
        operation so the two cannot drift. draft -> active is rejected: an IdP
        goes live only after somebody has logged in through it.
        """

        request_serializer = IdentityProviderTransitionSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        identity_provider = transition_identity_provider(
            self.get_object(), request_serializer.validated_data["state"]
        )

        return Response(self.get_serializer(identity_provider).data)


class ParseMetadataView(ProvisioningExceptionMixin, viewsets.ViewSet):
    """
    Parse IdP metadata without creating anything.

    Deliberately unnested: an operator (later, a wizard) pastes a metadata URL
    or document and sees what Keycloak makes of it before committing to a
    resource. Staff-only, and it stays that way in phase 1 - the URL form makes
    Keycloak fetch a caller-supplied address, which is an SSRF surface that
    needs an allowlist and a rate limit before it goes anywhere near a partner.
    """

    permission_classes = [IsAdminOrReadOnly]

    @extend_schema(
        request=ParseMetadataSerializer,
        responses={
            200: inline_serializer(
                name="ParsedIdentityProviderConfigSerializer",
                fields={"config": serializers.DictField(child=serializers.CharField())},
            ),
            502: DetailSerializer,
        },
    )
    def create(self, request):
        """Return the config map Keycloak parses out of the given metadata."""

        request_serializer = ParseMetadataSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        config = parse_identity_provider_metadata(
            request_serializer.validated_data["protocol"],
            metadata_url=request_serializer.validated_data.get("metadata_url"),
            metadata_xml=request_serializer.validated_data.get("metadata_xml"),
        )

        return Response({"config": config})
