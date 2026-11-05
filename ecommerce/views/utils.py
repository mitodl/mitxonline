"""View code shared by the legacy and v0 ecommerce API stacks."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from ecommerce.models import Discount, DiscountProduct, Product


class AttachDiscountProductMixin:
    """
    partial_update for a viewset nested under a discount: link the product
    named by `product_id` to that discount and answer with the discount's full
    product list, serialized by the viewset's own serializer_class.

    The method docstring is the operation's description in the OpenAPI spec.
    """

    def partial_update(self, request, **kwargs):
        """Partial update for a discount product."""
        discount = get_object_or_404(Discount, pk=kwargs["parent_lookup_discount"])

        product = get_object_or_404(Product.objects, pk=request.data["product_id"])

        try:
            (_, created) = DiscountProduct.objects.get_or_create(
                discount=discount, product=product
            )
        except DjangoValidationError as exc:
            return Response(
                {"error": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            self.get_serializer(
                DiscountProduct.objects.filter(discount=discount).all(), many=True
            ).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
