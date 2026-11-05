"""
Request serializers for MITx Online ecommerce.

These validate incoming request bodies and describe them in the OpenAPI schema.
"""

from rest_framework import serializers


class CreateBasketWithProductIDSerializer(serializers.Serializer):
    """Defines the schema for a product ID and quantity in the CreateBasketWithProductsSerializer."""

    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class CreateBasketWithProductsSerializer(serializers.Serializer):
    """Serializer for creating a basket with products."""

    product_ids = CreateBasketWithProductIDSerializer(many=True)
    checkout = serializers.BooleanField(required=False, default=False)
    # `null` and `""` both mean "no discount": the view treats any falsy code as
    # absent. CharField rejects both without allow_null/allow_blank.
    discount_code = serializers.CharField(
        required=False, default=None, allow_null=True, allow_blank=True
    )
