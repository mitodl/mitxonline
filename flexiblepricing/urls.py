from django.urls import path
from django.urls import include
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

urlpatterns = [
    path("api/v0/flexible_pricing/", include(router.urls)),
    path("api/flexible_pricing/", include(router.urls)),
]
