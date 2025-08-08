"""URL routing for v0 of the B2B API."""

from django.urls import include, path, re_path
from rest_framework.routers import SimpleRouter

from b2b.views.v0 import (
    AttachContractApi,
    ContractPageViewSet,
    Enroll,
    OrganizationPageViewSet,
)

app_name = "b2b"

v0_router = SimpleRouter()
v0_router.register(
    r"organizations",
    OrganizationPageViewSet,
    basename="b2b-organization",
)
v0_router.register(
    r"contracts",
    ContractPageViewSet,
    basename="b2b-contract",
)

urlpatterns = [
    re_path(r"^", include(v0_router.urls)),
    path(r"enroll/<str:readable_id>/", Enroll.as_view()),
    path(
        r"attach/<str:enrollment_code>/",
        AttachContractApi.as_view(),
        name="attach-user",
    ),
]
