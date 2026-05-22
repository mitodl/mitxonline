"""Serializers for variants."""

from rest_framework import serializers

from variants.models import SupportedVariant


class SupportedVariantSerializer(serializers.ModelSerializer):
    """Serializer for the SupportedVariant model."""

    class Meta:
        model = SupportedVariant
        fields = [
            "id",
            "language",
            "variant_length",
            "variant_industry",
            "active",
            "b2b_only",
            "default_variant",
        ]
        read_only_fields = [
            "id",
            "language",
            "variant_length",
            "variant_industry",
            "active",
            "b2b_only",
            "default_variant",
        ]
