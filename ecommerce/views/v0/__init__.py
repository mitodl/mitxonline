"""
MITx Online API-ready views, migrated from Unified Ecommerce.
"""

import logging

from django.shortcuts import redirect
from django_filters import rest_framework as filters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from ecommerce.api import (
    apply_discount_to_basket,
    establish_basket,
    get_auto_apply_discounts_for_basket,
)
from ecommerce.exceptions import ProductBlockedError
from ecommerce.models import Basket, BasketItem, Discount, Product
from ecommerce.serializers import BasketItemSerializer, BasketWithProductSerializer
from ecommerce.serializers.v0 import requests

log = logging.getLogger(__name__)


@extend_schema(
    description="Returns the basket items for the current user.",
    methods=["GET"],
    request=None,
    responses=BasketItemSerializer,
)
class BasketItemViewSet(ModelViewSet):
    """ViewSet for handling BasketItem operations."""

    permission_classes = (IsAuthenticated,)
    serializer_class = BasketItemSerializer

    def get_queryset(self):
        """Return only basket items owned by this user."""
        if getattr(self, "swagger_fake_view", False):
            return BasketItem.objects.none()

        return BasketItem.objects.filter(basket__user=self.request.user)


@extend_schema_view(
    list=extend_schema(
        description=("Retrives the current user's baskets."),
        parameters=[],
    ),
    retrieve=extend_schema(
        description="Retrieve a basket for the current user.",
        parameters=[
            OpenApiParameter("id", OpenApiTypes.INT, OpenApiParameter.PATH),
        ],
    ),
)
class BasketViewSet(ReadOnlyModelViewSet):
    """API view set for Basket"""

    serializer_class = BasketWithProductSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = (filters.DjangoFilterBackend,)

    def get_queryset(self):
        """Return only baskets owned by this user."""

        if getattr(self, "swagger_fake_view", False):
            return Basket.objects.none()

        return Basket.objects.filter(user=self.request.user).all()


@extend_schema(
    description=(
        "Creates or updates a basket for the current user, "
        "adding the discount if valid."
    ),
    methods=["POST"],
    request=None,
    responses=BasketWithProductSerializer,
    parameters=[
        OpenApiParameter("system_slug", OpenApiTypes.STR, OpenApiParameter.PATH),
        OpenApiParameter(
            "discount_code", OpenApiTypes.STR, OpenApiParameter.QUERY, required=True
        ),
    ],
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def add_discount_to_basket(request):
    """
    Add a discount to the basket for the currently logged in user.

    POST Args:
        discount_code (str): discount code to apply to the basket

    Returns:
        Response: HTTP response
    """
    basket = Basket.establish_basket(request)
    discount_code = request.query_params.get("discount_code")

    try:
        discount = Discount.objects.get(discount_code=discount_code)
    except Discount.DoesNotExist:
        return Response(
            {"error": f"Discount '{discount_code}' not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        apply_discount_to_basket(basket, discount)
    except ValueError:
        return Response(
            {"error": "An error occurred while applying the discount."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        BasketWithProductSerializer(basket).data,
        status=status.HTTP_200_OK,
    )


def _create_basket_from_product(
    request, product_id: int, discount_code: str | None = None
):
    """
    Create a new basket item from a product for the currently logged in user. Reuse
    the existing basket object if it exists.

    If the checkout flag is set in the POST data, then this will create the
    basket, then immediately flip the user to the checkout interstitial (which
    then redirects to the payment gateway).

    If the discount code is provided, then it will be applied to the basket. If
    the discount isn't found or doesn't apply, then it will be ignored.

    Args:
        request (Request): The request object.
        product_id (int): Product ID
        discount_code (str): Discount code
    POST Args:
        quantity (int): quantity of the product to add to the basket (defaults to 1)
        checkout (bool): redirect to checkout interstitial (defaults to False)

    Returns:
        Response: HTTP response
    """
    basket = establish_basket(request)
    quantity = request.data.get("quantity", 1)
    checkout = request.data.get("checkout", False)

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
        )

    # FUTURE: This is where the basket_add hook was called.

    (_, created) = BasketItem.objects.update_or_create(
        basket=basket, product=product, defaults={"quantity": quantity}
    )
    auto_apply_discount_discounts = get_auto_apply_discounts_for_basket(basket.id)
    for discount in auto_apply_discount_discounts:
        apply_discount_to_basket(basket, discount)

    if discount_code:
        try:
            discount = Discount.objects.get(discount_code=discount_code)
            apply_discount_to_basket(basket, discount)
        except Discount.DoesNotExist:
            pass

    basket.refresh_from_db()

    if checkout:
        return redirect("checkout_interstitial_page")

    return Response(
        BasketWithProductSerializer(basket).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(
    description=(
        "Creates or updates a basket for the current user, adding the selected product."
    ),
    methods=["POST"],
    request=None,
    responses=BasketWithProductSerializer,
    parameters=[
        OpenApiParameter(
            "product_id", OpenApiTypes.INT, OpenApiParameter.PATH, required=True
        ),
    ],
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def create_basket_from_product(request, product_id: int):
    """Run _create_basket_from_product."""

    return _create_basket_from_product(request, product_id)


@extend_schema(
    operation_id="create_basket_from_product_with_discount",
    description=(
        "Creates or updates a basket for the current user, "
        "adding the selected product and discount."
    ),
    methods=["POST"],
    request=None,
    responses=BasketWithProductSerializer,
    parameters=[
        OpenApiParameter(
            "product_id", OpenApiTypes.INT, OpenApiParameter.PATH, required=True
        ),
        OpenApiParameter(
            "discount_code", OpenApiTypes.STR, OpenApiParameter.PATH, required=True
        ),
    ],
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def create_basket_from_product_with_discount(
    request, product_id: int, discount_code: str | None = None
):
    """Run _create_basket_from_product with the discount code."""

    return _create_basket_from_product(request, product_id, discount_code)


@extend_schema(
    description=(
        "Creates or updates a basket for the current user, adding the selected product."
    ),
    methods=["POST"],
    responses=BasketWithProductSerializer,
    request=requests.CreateBasketWithProductsSerializer,
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def create_basket_with_products(request):
    """
    Create new basket items for the currently logged in user. Reuse the existing
    basket object if it exists. Optionally apply the specified discount.

    If the checkout flag is set in the POST data, then this will create the
    basket, then immediately flip the user to the checkout interstitial (which
    then redirects to the payment gateway).

    If any of the products aren't found, this will return a 404 error. If
    the discount code is invalid, the discount won't be applied and an error
    will be logged, but the basket will still be updated.

    POST Args:
        checkout (bool): redirect to checkout interstitial (defaults to False)
        product_ids (list[(str, int)]): list of product SKUs to add to the basket with quantity
        discount_code (str): discount code to apply to the basket

    Returns:
        Response: HTTP response
    """
    checkout = request.data.get("checkout", False)
    discount_code = request.data.get("discount_code", None)
    product_ids = request.data.get("product_ids", [])

    basket = establish_basket(request)
    products = []

    try:
        products = [
            (
                Product.objects.get(id=product_id["product_id"]),
                product_id["quantity"],
            )
            for product_id in product_ids
        ]
    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        for product, quantity in products:
            # FUTURE: this is where the basket_add hook is called
            BasketItem.objects.update_or_create(
                basket=basket, product=product, defaults={"quantity": quantity}
            )
    except ProductBlockedError:
        return Response(
            {"error": "Product blocked from purchasing.", "product": product},
            status=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
        )

    auto_apply_discounts = get_auto_apply_discounts_for_basket(basket.id)
    for discount in auto_apply_discounts:
        apply_discount_to_basket(basket, discount, allow_finaid=True)

    if discount_code:
        try:
            discount = Discount.objects.get(discount_code=discount_code)
            apply_discount_to_basket(basket, discount)
        except Discount.DoesNotExist:
            pass

    basket.refresh_from_db()

    if checkout:
        return redirect("checkout_interstitial_page")

    return Response(
        BasketWithProductSerializer(basket).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    description="Clears the basket for the current user.",
    methods=["DELETE"],
    request=None,
    responses={204: OpenApiResponse(description="Basket cleared successfully")},
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def clear_basket(request):
    """
    Clear the basket for the current user.

    Args:
        system_slug (str): system slug

    Returns:
        Response: HTTP response
    """
    basket = establish_basket(request)

    basket.delete()

    return Response(None, status=status.HTTP_204_NO_CONTENT)
