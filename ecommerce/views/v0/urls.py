"""Ecommerce v0 URLs."""

from django.urls import include, path, re_path

from ecommerce.views.v0 import (
    AllProductViewSet,
    BasketItemViewSet,
    BasketViewSet,
    DiscountViewSet,
    NestedDiscountProductViewSet,
    NestedDiscountRedemptionViewSet,
    NestedDiscountTierViewSet,
    NestedUserDiscountViewSet,
    ProductViewSet,
    add_discount_to_basket,
    clear_basket,
    create_basket_from_product,
    create_basket_from_product_with_discount,
    create_basket_with_products,
)
from main.routers import SimpleRouterWithNesting

router = SimpleRouterWithNesting()

router.register(r"products/all", AllProductViewSet, basename="all_products_api")
router.register(r"products", ProductViewSet, basename="products_api")

basket_router = router.register(r"baskets", BasketViewSet, basename="baskets_api")
basket_router.register(
    r"items",
    BasketItemViewSet,
    basename="baskets_api-items",
    parents_query_lookups=["basket"],
)

discountsRouter = router.register(  # noqa: N816
    r"discounts", DiscountViewSet, basename="discounts_api"
)
discountsRouter.register(
    r"redemptions",
    NestedDiscountRedemptionViewSet,
    basename="discounts_api-redemptions",
    parents_query_lookups=["redeemed_discount"],
)
discountsRouter.register(
    r"assignees",
    NestedUserDiscountViewSet,
    basename="discounts_api-assignees",
    parents_query_lookups=["discount"],
)
discountsRouter.register(
    r"products",
    NestedDiscountProductViewSet,
    basename="discounts_api-products",
    parents_query_lookups=["discount"],
)
discountsRouter.register(
    r"tiers",
    NestedDiscountTierViewSet,
    basename="discounts_api-tiers",
    parents_query_lookups=["discount"],
)

urlpatterns = [
    path(
        "baskets/create_from_product/<str:product_id>/",
        create_basket_from_product,
        name="baskets_api-create_from_product",
    ),
    path(
        "baskets/create_from_product/<str:product_id>/<str:discount_code>/",
        create_basket_from_product_with_discount,
        name="baskets_api-create_from_product_with_discount",
    ),
    path(
        "baskets/create_with_products/",
        create_basket_with_products,
        name="baskets_api-create_with_products",
    ),
    path(
        "baskets/clear/",
        clear_basket,
        name="baskets_api-clear_basket",
    ),
    path(
        "baskets/add_discount/",
        add_discount_to_basket,
        name="baskets_api-add_discount",
    ),
    re_path(
        r"^",
        include(
            router.urls,
        ),
    ),
]
