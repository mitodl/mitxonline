from django.urls import include, re_path, path
from rest_framework_extensions.routers import NestedRouterMixin
from rest_framework.routers import SimpleRouter

from courses.views.v1 import create_enrollment_view

""" TODO: clean this up later (make the views look more like the courses one) """
from ecommerce.views.v0 import ProductViewSet, BasketViewSet, BasketItemViewSet


class SimpleRouterWithNesting(NestedRouterMixin, SimpleRouter):
    pass


router = SimpleRouterWithNesting()

router.register(r"products", ProductViewSet, basename="products_api")

router.register(
    r'basket', BasketViewSet, basename='basket'
).register(
    r'items',
    BasketItemViewSet,
    basename='basket-items',
    parents_query_lookups=['basket_items']
)

urlpatterns = [
    re_path(r"^api/v0/", include(router.urls)),
    re_path(r"^api/", include(router.urls)),
    path("add_product/", create_enrollment_view, name="add-product-to-basket"),
]
