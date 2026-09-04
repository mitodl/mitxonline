"""URL routing for v0 of the B2B API."""

from django.urls import include, path

from b2b.views.v0 import (
    AttachContractApi,
    ContractPageViewSet,
    Enroll,
    OrganizationPageViewSet,
)
from b2b.views.v0.manager import (
    ManagerContractViewSet,
    ManagerOrganizationViewSet,
    ProcessMailgunWebhook,
)
from b2b.views.v0.provisioning import (
    IdentityProviderProvisioningViewSet,
    OrganizationProvisioningViewSet,
    ParseMetadataView,
)
from b2b.views.v0.service import OrganizationManagerCheckView
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

# Staff-only provisioning routes (capability C1). These take ownership of
# per-customer Keycloak resources from Pulumi; see
# docs/source/b2b/provisioning_api.md.
provisioning_org = v0_router.register(
    r"provisioning/organizations",
    OrganizationProvisioningViewSet,
    basename="b2b-provisioning-organization",
)
provisioning_org.register(
    r"identity-providers",
    IdentityProviderProvisioningViewSet,
    basename="b2b-provisioning-organization-idp",
    parents_query_lookups=[
        "organization__org_key",
    ],
)
v0_router.register(
    r"provisioning/parse-metadata",
    ParseMetadataView,
    basename="b2b-provisioning-parse-metadata",
)

urlpatterns = [
    path("", include(v0_router.urls)),
    path(r"enroll/<str:readable_id>/", Enroll.as_view(), name="enroll-user"),
    path(
        r"attach/<str:enrollment_code>/",
        AttachContractApi.as_view(),
        name="attach-user",
    ),
    # Probably not the place this is gonna live long term.
    path(r"webhook", ProcessMailgunWebhook.as_view(), name="mailgun-webhook"),
    # Service-to-service; delete along with b2b/views/v0/service.py once
    # org-manager status is visible in Keycloak (mitodl/hq#10594).
    path(
        r"service/organization-manager-check/",
        OrganizationManagerCheckView.as_view(),
        name="service-organization-manager-check",
    ),
]
