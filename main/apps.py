"""
Django app
"""
from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class RootConfig(AppConfig):
    """AppConfig for this project"""

    name = "main"

    def ready(self):
        from mitol.common import envs

        envs.validate()
