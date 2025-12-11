"""Customized URL routers for the application."""

from rest_framework.routers import SimpleRouter
from rest_framework_extensions.routers import NestedRouterMixin


class SimpleRouterWithNesting(NestedRouterMixin, SimpleRouter):
    pass
