"""
Django app
"""

from django.apps import AppConfig


class RootConfig(AppConfig):
    """AppConfig for this project"""

    name = "main"

    def ready(self):
        from mitol.common import envs  # noqa: PLC0415
        from mitol.olposthog.features import configure  # noqa: PLC0415

        envs.validate()
        configure()

        from main.telemetry import configure_opentelemetry  # noqa: PLC0415

        configure_opentelemetry()
