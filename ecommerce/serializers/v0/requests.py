"""
Request serializers for MITx Online ecommerce.

Request serializers are used for OpenAPI schema generation - so separating them
out so they don't get used for responses.
"""

from rest_framework import serializers


class CreateBasketWithProductIDSerializer(serializers.Serializer):
    """Defines the schema for a product ID and quantity in the CreateBasketWithProductsSerializer."""

    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class CreateBasketWithProductsSerializer(serializers.Serializer):
    """Serializer for creating a basket with products. (For OpenAPI spec.)"""

    system_slug = serializers.CharField()
    product_ids = CreateBasketWithProductIDSerializer(many=True)
    checkout = serializers.BooleanField()
    discount_code = serializers.CharField()
