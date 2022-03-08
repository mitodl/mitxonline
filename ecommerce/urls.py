from django.urls import include, re_path
from rest_framework_extensions.routers import NestedRouterMixin
from rest_framework.routers import SimpleRouter


""" TODO: clean this up later (make the views look more like the courses one) """
from ecommerce.views.v0 import (
    ProductViewSet,
    BasketViewSet,
    BasketItemViewSet,
    CheckoutCallbackView,
    BasketDiscountViewSet,
    CheckoutApiViewSet,
    CheckoutInterstitialView,
    CheckoutProductView,
    OrderHistoryViewSet,
)


class SimpleRouterWithNesting(NestedRouterMixin, SimpleRouter):
    pass


router = SimpleRouterWithNesting()
router.register(r"products", ProductViewSet, basename="products_api")
router.register(r"checkout", CheckoutApiViewSet, basename="checkout_api")
router.register(r"orders/history", OrderHistoryViewSet, basename="orderhistory_api")

basketRouter = router.register(r"baskets", BasketViewSet, basename="basket")
basketRouter.register(
    r"items",
    BasketItemViewSet,
    basename="basket-items",
    parents_query_lookups=["basket"],
)
basketRouter.register(
    r"discounts",
    BasketDiscountViewSet,
    basename="basket-discounts",
    parents_query_lookups=["basket"],
)

urlpatterns = [
    re_path(r"^api/v0/", include(router.urls)),
    re_path(r"^api/", include(router.urls)),
    re_path(
        "checkout/to_payment",
        CheckoutInterstitialView.as_view(),
        name="checkout_interstitial_page",
    ),
    re_path(
        r"^checkout/result/",
        CheckoutCallbackView.as_view(),
        name="checkout-result-callback",
    ),
    re_path(r"^cart/add", CheckoutProductView.as_view(), name="checkout-product"),
]
