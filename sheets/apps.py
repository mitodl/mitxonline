"""
Django App
"""

from django.apps import AppConfig


class SheetsConfig(AppConfig):
    """AppConfig for Sheets"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "sheets"
