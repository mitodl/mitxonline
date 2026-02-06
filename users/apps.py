from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Config for users app"""

    name = "users"

    def ready(self):
        """Import signals when the app is ready"""
        import users.signals  # noqa: F401
