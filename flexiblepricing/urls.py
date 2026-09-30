from django.urls import include, path
from rest_framework.routers import SimpleRouter
from rest_framework_extensions.routers import NestedRouterMixin

from flexiblepricing.views.v0 import (
    FlexiblePriceAdminViewSet,
    FlexiblePriceCoursewareViewSet,
)


class SimpleRouterWithNesting(NestedRouterMixin, SimpleRouter):
    pass


router = SimpleRouterWithNesting()
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
