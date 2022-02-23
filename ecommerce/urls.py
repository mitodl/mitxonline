from django.urls import include, re_path, path
from main import features
from rest_framework_extensions.routers import NestedRouterMixin
from rest_framework.routers import SimpleRouter


""" TODO: clean this up later (make the views look more like the courses one) """
from ecommerce.views.v0 import (
    ProductViewSet,
    BasketViewSet,
    BasketItemViewSet,
    CheckoutViewSet,
    CheckoutApiViewSet,
    CheckoutInterstitialView,
    CheckoutTestView,
    CheckoutTestStepTwoView,
    CheckoutDecodeResponseView,
)


class SimpleRouterWithNesting(NestedRouterMixin, SimpleRouter):
    pass


router = SimpleRouterWithNesting()

frontend_router = SimpleRouter()

router.register(r"products", ProductViewSet, basename="products_api")
router.register(r"checkout", CheckoutApiViewSet, basename="checkout_api")

frontend_router.register(r"checkout", CheckoutViewSet, basename="checkout")

router.register(r"baskets", BasketViewSet, basename="basket").register(
    r"items",
    BasketItemViewSet,
    basename="basket-items",
    parents_query_lookups=["basket"],
)

urlpatterns = [
    re_path(r"^api/v0/", include(router.urls)),
    re_path(r"^api/", include(router.urls)),
    re_path(r"^ecommerce/", include(frontend_router.urls)),
    re_path(
        "checkout/to_payment",
        CheckoutInterstitialView.as_view(),
        name="checkout_interstitial_page",
    ),
]

if features.is_enabled(features.CHECKOUT_TEST_UI):
    urlpatterns += [
        path(
            "ecommerce-test/checkout/",
            CheckoutTestView.as_view(),
            name="checkout_test_step1",
        ),
        path(
            "ecommerce-test/checkout_complete/",
            CheckoutTestStepTwoView.as_view(),
            name="checkout_test_step2",
        ),
        path(
            "ecommerce-test/checkout_decode_response/",
            CheckoutDecodeResponseView.as_view(),
            name="checkout_test_decode_response",
        ),
    ]
