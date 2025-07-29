from django.apps import AppConfig
from wagtail.users.apps import WagtailUsersAppConfig


class CmsConfig(AppConfig):
    name = "cms"

    def ready(self):
        pass


class CustomWagtailUsersAppConfig(WagtailUsersAppConfig):
    """
    Custom Wagtail Users AppConfig to ensure it uses our custom User model.
    """

    user_viewset = "cms.views.WagtailUsersViewSet"
