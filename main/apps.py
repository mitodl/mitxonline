"""
Django app
"""
from django.apps import AppConfig


class RootConfig(AppConfig):
    """AppConfig for this project"""

    name = "main"

    def ready(self):
        from mitol.common import envs
        from mitol.posthog.features import configure

        envs.validate()
        configure()
