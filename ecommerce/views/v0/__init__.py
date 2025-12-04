"""
MITx Online API-ready views, migrated from Unified Ecommerce.
"""

import logging
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_filters import rest_framework as filters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from mitol.payment_gateway.api import PaymentGateway
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from ecommerce.api import establish_basket, get_auto_apply_discounts_for_basket
from ecommerce.models import Basket, BasketDiscount, BasketItem, Discount, Product
from ecommerce.serializers import BasketSerializer, BasketWithProductSerializer

log = logging.getLogger(__name__)


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


def _create_basket_from_product(
    request, sku: str, discount_code: str|None = None
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
        sku (str): Product ID
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
        product = Product.objects.get(id=sku)
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
        basket.apply_discount_to_basket(discount)

    if discount_code:
        try:
            discount = Discount.objects.get(discount_code=discount_code)
            basket.apply_discount_to_basket(discount)
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
            "system_slug", OpenApiTypes.STR, OpenApiParameter.PATH, required=True
        ),
        OpenApiParameter("sku", OpenApiTypes.STR, OpenApiParameter.PATH, required=True),
    ],
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def create_basket_from_product(request, system_slug: str, sku: str):
    """Run _create_basket_from_product."""

    return _create_basket_from_product(request, system_slug, sku)


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
            "system_slug", OpenApiTypes.STR, OpenApiParameter.PATH, required=True
        ),
        OpenApiParameter("sku", OpenApiTypes.STR, OpenApiParameter.PATH, required=True),
        OpenApiParameter(
            "discount_code", OpenApiTypes.STR, OpenApiParameter.PATH, required=True
        ),
    ],
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def create_basket_from_product_with_discount(
    request, system_slug: str, sku: str, discount_code: Optional[str] = None
):
    """Run _create_basket_from_product with the discount code."""

    return _create_basket_from_product(request, system_slug, sku, discount_code)


@extend_schema(
    description=(
        "Creates or updates a basket for the current user, adding the selected product."
    ),
    methods=["POST"],
    responses=BasketWithProductSerializer,
    request=CreateBasketWithProductsSerializer,
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
        system_slug (str): system slug
        quantity (int): quantity of the product to add to the basket (defaults to 1)
        checkout (bool): redirect to checkout interstitial (defaults to False)
        skus (list[str]): list of product SKUs to add to the basket
        discount_code (str): discount code to apply to the basket

    Returns:
        Response: HTTP response
    """
    system_slug = request.data.get("system_slug")
    checkout = request.data.get("checkout", False)
    discount_code = request.data.get("discount_code", None)
    skus = request.data.get("skus", [])

    system = IntegratedSystem.objects.get(slug=system_slug)
    basket = Basket.establish_basket(request, system)
    products = []

    try:
        products = [
            (
                Product.objects.get(system=system, sku=sku["sku"]),
                sku["quantity"],
            )
            for sku in skus
        ]
    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        for product, quantity in products:
            pm.hook.basket_add(request=request, basket=basket, basket_item=product)
            BasketItem.objects.update_or_create(
                basket=basket, product=product, defaults={"quantity": quantity}
            )
    except ProductBlockedError:
        return Response(
            {"error": "Product blocked from purchasing.", "product": product},
            status=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
        )

    auto_apply_discount_discounts = api.get_auto_apply_discounts_for_basket(basket.id)
    for discount in auto_apply_discount_discounts:
        basket.apply_discount_to_basket(discount)

    if discount_code:
        try:
            discount = Discount.objects.get(discount_code=discount_code)
            basket.apply_discount_to_basket(discount)
        except Discount.DoesNotExist:
            pass

    basket.refresh_from_db()

    if checkout:
        return redirect("checkout_interstitial_page", system_slug=system.slug)

    return Response(
        BasketWithProductSerializer(basket).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    description="Clears the basket for the current user.",
    methods=["DELETE"],
    versions=["v0"],
    responses=OpenApiResponse(Response(None, status=status.HTTP_204_NO_CONTENT)),
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def clear_basket(request, system_slug: str):
    """
    Clear the basket for the current user.

    Args:
        system_slug (str): system slug

    Returns:
        Response: HTTP response
    """
    system = IntegratedSystem.objects.get(slug=system_slug)
    basket = Basket.establish_basket(request, system)

    basket.delete()

    return Response(None, status=status.HTTP_204_NO_CONTENT)
