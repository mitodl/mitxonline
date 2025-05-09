"""
Django app
"""

from django.apps import AppConfig


class RootConfig(AppConfig):
    """AppConfig for this project"""

    name = "main"

    def ready(self):
        from mitol.common import envs
        from mitol.olposthog.features import configure

        envs.validate()
        configure()

        from main.telemetry import configure_opentelemetry

        configure_opentelemetry()
