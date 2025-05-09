"""Serializers for the B2B API (v0)."""

from rest_framework import serializers

from b2b.models import ContractPage, OrganizationPage


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
