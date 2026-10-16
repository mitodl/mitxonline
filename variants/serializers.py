"""Serializers for variants."""

from rest_framework import serializers

from variants.models import SupportedVariant


class SupportedVariantSerializer(serializers.ModelSerializer):
    """Serializer for the SupportedVariant model."""

    class Meta:
        model = SupportedVariant
        fields = [
            "language",
            "variant_length",
            "variant_industry",
            "variant_length_label",
            "variant_industry_label",
            "active",
            "b2b_only",
            "default_variant",
        ]
        read_only_fields = [
            "language",
            "variant_length",
            "variant_industry",
            "variant_length_label",
            "variant_industry_label",
            "active",
            "b2b_only",
            "default_variant",
        ]
