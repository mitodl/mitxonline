from django.urls import include, path
from rest_framework.routers import SimpleRouter
from rest_framework_extensions.routers import NestedRouterMixin

from flexiblepricing.views.v0 import (
    CountryIncomeThresholdViewSet,
    CurrencyExchangeRateViewSet,
    FlexiblePriceAdminViewSet,
    FlexiblePriceCoursewareViewSet,
    FlexiblePriceViewSet,
)


class SimpleRouterWithNesting(NestedRouterMixin, SimpleRouter):
    pass


router = SimpleRouterWithNesting()
router.register(
    r"exchange_rates", CurrencyExchangeRateViewSet, basename="fp_exchangerates_api"
)
router.register(
    r"income_thresholds",
    CountryIncomeThresholdViewSet,
    basename="fp_countryincomethresholds_api",
)
router.register(
    r"applications", FlexiblePriceViewSet, basename="fp_flexiblepricing_api"
)
router.register(
    r"applications_admin",
    FlexiblePriceAdminViewSet,
    basename="fp_admin_flexiblepricing_api",
)

router.register(
    r"coursewares",
    FlexiblePriceCoursewareViewSet,
    basename="fp_flexiblepricing_coursewares_api",
)

# Nested so the resolved namespace is "flexiblepricing:v0" rather than a
# bare "v0" - ecommerce's urls.py already owns the top-level "v0"
# namespace, and NamespaceVersioning only needs "v0" to appear somewhere
# in the colon-split chain, not to be the whole thing.
_v0_patterns = [
    path("", include((router.urls, "v0"), namespace="v0")),
]

urlpatterns = [
    path(
        "api/v0/flexible_pricing/",
        include((_v0_patterns, "flexiblepricing"), namespace="flexiblepricing"),
    ),
    path("api/flexible_pricing/", include(router.urls)),
]
