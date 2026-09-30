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

        from main.cybersource_compat import (  # noqa: PLC0415
            apply_cybersource_urllib3_compat,
        )

        envs.validate()
        configure()
        apply_cybersource_urllib3_compat()
