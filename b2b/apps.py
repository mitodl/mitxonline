"""Configuration for the B2B application."""

from django.apps import AppConfig


class B2BConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "b2b"

    def ready(self):
        """Import signals when the app is ready"""
        import b2b.signals  # noqa: F401, PLC0415
