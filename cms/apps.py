from django.apps import AppConfig
from wagtail.users.apps import WagtailUsersAppConfig


class CmsConfig(AppConfig):
    name = "cms"
    default = True  # This file has two app configs, so we need to specify the default.

    def ready(self):
        import cms.signals  # noqa: F401, PLC0415


class CustomWagtailUsersAppConfig(WagtailUsersAppConfig):
    """
    Custom Wagtail Users AppConfig to ensure it uses our custom User model.
    """

    user_viewset = "cms.views.WagtailUsersViewSet"
