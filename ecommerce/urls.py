from django.urls import include, re_path, path
from rest_framework import routers

""" TODO: clean this up later (make the views look more like the courses one) """
from ecommerce.views.v0 import ProductViewSet

router = routers.SimpleRouter()

router.register(r"products", ProductViewSet, basename="products_api")

urlpatterns = [
    re_path(r"^api/v0/", include(router.urls)),
    re_path(r"^api/", include(router.urls)),
]
