"""Ecommerce v0 URLs."""

from django.urls import include, path, re_path

from ecommerce.views.v0 import (
    BasketItemViewSet,
    BasketViewSet,
    add_discount_to_basket,
    clear_basket,
    create_basket_from_product,
    create_basket_from_product_with_discount,
    create_basket_with_products,
)
from main.routers import SimpleRouterWithNesting

router = SimpleRouterWithNesting()

basket_router = router.register(r"baskets", BasketViewSet, basename="basket")
backet_item_router = router.register(
    r"basketitems", BasketItemViewSet, basename="basketitem"
)

urlpatterns = [
    path(
        "baskets/create_from_product/<str:product_id>/",
        create_basket_from_product,
        name="create_from_product",
    ),
    path(
        "baskets/create_from_product/<str:product_id>/<str:discount_code>/",
        create_basket_from_product_with_discount,
        name="create_from_product_with_discount",
    ),
    path(
        "baskets/create_with_products/",
        create_basket_with_products,
        name="create_with_products",
    ),
    path(
        "baskets/clear/",
        clear_basket,
        name="clear_basket",
    ),
    path(
        "baskets/add_discount/",
        add_discount_to_basket,
        name="add_discount",
    ),
    re_path(
        r"^",
        include(
            router.urls,
        ),
    ),
]
