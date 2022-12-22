from django.apps import AppConfig


class EcommerceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ecommerce"

    def ready(self):
        """Application is ready"""
        import ecommerce.signals  # pylint:disable=unused-import, unused-variable
