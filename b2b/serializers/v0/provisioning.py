"""Serializers for the staff-only B2B provisioning API (v0)."""

from rest_framework import serializers

from b2b.constants import (
    IDP_LIFECYCLE_CHOICES,
    IDP_PROTOCOL_CHOICES,
    IDP_PROTOCOL_OIDC,
    IDP_PROTOCOL_SAML,
    ONBOARDING_STATE_CHOICES,
)
from b2b.models import (
    OrganizationIdentityProvider,
    OrganizationOnboarding,
    OrganizationPage,
)


class OrganizationOnboardingSerializer(serializers.ModelSerializer):
    """Where an organization is in the onboarding sequence."""

    class Meta:
        model = OrganizationOnboarding
        fields = ["state", "state_changed_at", "notes"]
        read_only_fields = ["state_changed_at"]


class OrganizationIdentityProviderSerializer(serializers.ModelSerializer):
    """
    An identity provider we provisioned for an organization.

    metadata_artifact is what Keycloak parsed out of the partner's metadata.
    Credentials are never written to it, so this is safe to serve.
    """

    class Meta:
        model = OrganizationIdentityProvider
        fields = [
            "id",
            "alias",
            "protocol",
            "display_name",
            "lifecycle_state",
            "internal_id",
            "metadata_source",
            "metadata_artifact",
            "metadata_fetched_at",
            "created_on",
            "updated_on",
        ]
        read_only_fields = fields


class ProvisionedOrganizationSerializer(serializers.ModelSerializer):
    """
    An organization as the provisioning API sees it.

    `domains` and `redirect_url` live only in Keycloak, so they are populated
    from the representation the view fetched rather than from our database.
    """

    onboarding = OrganizationOnboardingSerializer(read_only=True)
    identity_providers = OrganizationIdentityProviderSerializer(
        many=True, read_only=True
    )
    domains = serializers.SerializerMethodField()
    redirect_url = serializers.SerializerMethodField()

    def get_domains(self, instance) -> list[str] | None:
        """Return the organization's Keycloak domains, if they were fetched."""

        keycloak_org = getattr(instance, "keycloak_organization", None)
        if keycloak_org is None:
            return None
        return [domain.name for domain in keycloak_org.domains or []]

    def get_redirect_url(self, instance) -> str | None:
        """Return the organization's Keycloak redirect URL, if it was fetched."""

        keycloak_org = getattr(instance, "keycloak_organization", None)
        return keycloak_org.redirect_url if keycloak_org else None

    class Meta:
        model = OrganizationPage
        fields = [
            "id",
            "name",
            "org_key",
            "org_key_prefix",
            "description",
            "slug",
            "sso_organization_id",
            "domains",
            "redirect_url",
            "onboarding",
            "identity_providers",
        ]
        read_only_fields = fields


class CreateOrganizationSerializer(serializers.Serializer):
    """Request body for provisioning a new organization."""

    name = serializers.CharField(max_length=255)
    org_key = serializers.CharField(max_length=30)
    org_key_prefix = serializers.CharField(
        max_length=30, required=False, allow_blank=True
    )
    domains = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    description = serializers.CharField(required=False, allow_blank=True, default="")
    redirect_url = serializers.CharField(required=False, allow_blank=True, default="")


class UpdateOrganizationSerializer(serializers.Serializer):
    """
    Request body for updating an organization.

    org_key is rejected rather than silently ignored. It is in every B2B
    courseware ID via create_contract_run_key, so a caller who thinks they
    changed it and did not is worse off than one who got an error.
    """

    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    redirect_url = serializers.CharField(required=False, allow_blank=True)
    domains = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        """Reject any attempt to change the immutable org key."""

        if "org_key" in self.initial_data:
            msg = (
                "org_key is immutable: it is part of every courseware ID for "
                "this organization."
            )
            raise serializers.ValidationError({"org_key": msg})
        return attrs


class ParseMetadataSerializer(serializers.Serializer):
    """
    Request body for parsing IdP metadata without creating anything.

    Exactly one of metadata_url or metadata_xml.
    """

    protocol = serializers.ChoiceField(choices=IDP_PROTOCOL_CHOICES)
    metadata_url = serializers.URLField(required=False, allow_blank=True)
    metadata_xml = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        """Require exactly one metadata source."""

        has_url = bool(attrs.get("metadata_url"))
        has_xml = bool(attrs.get("metadata_xml"))

        if has_url == has_xml:
            msg = "Supply exactly one of metadata_url or metadata_xml."
            raise serializers.ValidationError(msg)

        return attrs


class CreateIdentityProviderSerializer(serializers.Serializer):
    """Request body for provisioning an identity provider."""

    alias = serializers.CharField(max_length=255)
    protocol = serializers.ChoiceField(choices=IDP_PROTOCOL_CHOICES)
    display_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    metadata_url = serializers.URLField(required=False, allow_blank=True)
    metadata_xml = serializers.CharField(required=False, allow_blank=True)
    discovery_url = serializers.URLField(required=False, allow_blank=True)
    client_id = serializers.CharField(required=False, allow_blank=True)
    client_secret = serializers.CharField(required=False, allow_blank=True)
    attribute_map = serializers.DictField(
        child=serializers.CharField(), required=False, default=dict
    )
    attribute_name_map = serializers.DictField(
        child=serializers.CharField(), required=False, default=dict
    )

    def validate(self, attrs):
        """Check that the protocol has the inputs it needs, and only those."""

        protocol = attrs["protocol"]

        if protocol == IDP_PROTOCOL_OIDC:
            if not attrs.get("discovery_url"):
                msg = "discovery_url is required for an OIDC identity provider."
                raise serializers.ValidationError({"discovery_url": msg})
            if not attrs.get("client_id") or not attrs.get("client_secret"):
                msg = (
                    "client_id and client_secret are required for an OIDC "
                    "identity provider."
                )
                raise serializers.ValidationError(msg)
            # The saga takes one metadata source regardless of protocol; for
            # OIDC that source is the discovery document.
            attrs["metadata_url"] = attrs["discovery_url"]
        elif protocol == IDP_PROTOCOL_SAML:
            if bool(attrs.get("metadata_url")) == bool(attrs.get("metadata_xml")):
                msg = (
                    "Supply exactly one of metadata_url or metadata_xml for a "
                    "SAML identity provider."
                )
                raise serializers.ValidationError(msg)

        if not attrs.get("attribute_map") and not attrs.get("attribute_name_map"):
            msg = "Supply attribute_map or attribute_name_map."
            raise serializers.ValidationError(msg)

        return attrs


class IdentityProviderTransitionSerializer(serializers.Serializer):
    """Request body for moving an identity provider's lifecycle state."""

    state = serializers.ChoiceField(choices=IDP_LIFECYCLE_CHOICES)


class SetOnboardingStateSerializer(serializers.Serializer):
    """Request body for recording an organization's onboarding state."""

    state = serializers.ChoiceField(choices=ONBOARDING_STATE_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
