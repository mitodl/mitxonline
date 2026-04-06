"""URL routing for v0 of the B2B API."""

from django.urls import include, path, re_path

from b2b.views.v0 import (
    AttachContractApi,
    ContractPageViewSet,
    Enroll,
    OrganizationPageViewSet,
)
from b2b.views.v0.manager import (
    ManagerContractViewSet,
    ManagerOrganizationViewSet,
)
from main.routers import SimpleRouterWithNesting

app_name = "b2b"

v0_router = SimpleRouterWithNesting()
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

# Manager dashboard routes
manager_org = v0_router.register(
    r"manager/organizations",
    ManagerOrganizationViewSet,
    basename="b2b-manager-organization",
)
manager_org.register(
    r"contracts",
    ManagerContractViewSet,
    basename="b2b-manager-org-contract",
    parents_query_lookups=[
        "organization",
    ],
)

urlpatterns = [
    re_path(r"^", include(v0_router.urls)),
    path(r"enroll/<str:readable_id>/", Enroll.as_view(), name="enroll-user"),
    path(
        r"attach/<str:enrollment_code>/",
        AttachContractApi.as_view(),
        name="attach-user",
    ),
]
