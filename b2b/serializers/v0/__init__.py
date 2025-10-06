"""Serializers for the B2B API (v0)."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from b2b.models import ContractPage, OrganizationPage, UserOrganization
from cms.api import get_wagtail_img_src
from main.constants import USER_MSG_TYPE_B2B_CHOICES


class ContractPageSerializer(serializers.ModelSerializer):
    """
    Serializer for the ContractPage model.
    """

    class Meta:
        model = ContractPage
        fields = [
            "id",
            "name",
            "description",
            "integration_type",
            "membership_type",
            "organization",
            "contract_start",
            "contract_end",
            "active",
            "slug",
            "organization",
        ]
        read_only_fields = [
            "id",
            "name",
            "description",
            "integration_type",
            "membership_type",
            "organization",
            "contract_start",
            "contract_end",
            "active",
            "slug",
            "organization",
        ]


class OrganizationPageSerializer(serializers.ModelSerializer):
    """
    Serializer for the OrganizationPage model.
    """

    contracts = ContractPageSerializer(many=True, read_only=True)

    class Meta:
        model = OrganizationPage
        fields = [
            "id",
            "name",
            "description",
            "logo",
            "slug",
            "contracts",
        ]
        read_only_fields = [
            "id",
            "name",
            "description",
            "logo",
            "slug",
            "contracts",
        ]


class GenerateCheckoutPayloadSerializer(serializers.Serializer):
    """
    Serializer for the result from ecommerce.api.generate_checkout_payload.

    The B2B enrollment API will return the result of the checkout call if the
    user needs to pay for the cart because of an error creating the checkout
    payload. In that case, we really just need the error states; it will also
    include a HttpResponseRedirect that we don't really care about for the API's
    purposes.
    """

    country_blocked = serializers.BooleanField(
        default=False, allow_null=True, required=False
    )
    purchased_same_courserun = serializers.BooleanField(
        default=False, allow_null=True, required=False
    )
    purchased_non_upgradeable_courserun = serializers.BooleanField(
        default=False, allow_null=True, required=False
    )
    invalid_discounts = serializers.BooleanField(
        default=False, allow_null=True, required=False
    )
    no_checkout = serializers.BooleanField(
        default=False, allow_null=True, required=False
    )


class CreateB2BEnrollmentSerializer(serializers.Serializer):
    """
    Serializer for the result from create_b2b_enrollment.

    There's always a result, and it should be one of the B2B messages that are
    defined in main.constants. The other fields appear or not depending on the
    result type.
    """

    result = serializers.ChoiceField(choices=USER_MSG_TYPE_B2B_CHOICES, read_only=True)
    order = serializers.IntegerField(read_only=True, required=False)
    price = serializers.DecimalField(
        max_digits=None, decimal_places=2, read_only=True, required=False
    )
    checkout_result = GenerateCheckoutPayloadSerializer(required=False)


class UserOrganizationSerializer(serializers.ModelSerializer):
    """
    Serializer for user organization data.

    Return the user's organizations in a manner that makes them look like
    OrganizationPage objects. (Previously, the user organizations were a queryset
    of OrganizationPages that related to the user, but now we have a through
    table.)
    """

    contracts = serializers.SerializerMethodField()
    id = serializers.IntegerField(source="organization.id")
    name = serializers.CharField(source="organization.name")
    description = serializers.CharField(source="organization.description")
    logo = serializers.SerializerMethodField()
    slug = serializers.CharField(source="organization.slug")

    @extend_schema_field(ContractPageSerializer(many=True))
    def get_contracts(self, instance):
        """Get the contracts for the organization for the user"""
        contracts = (
            self.context["user"]
            .b2b_contracts.filter(
                organization=instance.organization,
            )
            .all()
        )
        return ContractPageSerializer(contracts, many=True).data

    @extend_schema_field(str)
    def get_logo(self, instance):
        """Get logo"""

        if hasattr(instance.organization, "logo"):
            try:
                return get_wagtail_img_src(instance.organization.logo)
            except AttributeError:
                pass

        return None

    class Meta:
        """Meta opts for the serializer."""

        model = UserOrganization
        fields = [
            "id",
            "name",
            "description",
            "logo",
            "slug",
            "contracts",
        ]
        read_only_fields = [
            "id",
            "name",
            "description",
            "logo",
            "slug",
            "contracts",
        ]
