"""
Django App
"""
from django.apps import AppConfig


class CoursesConfig(AppConfig):
    """AppConfig for Courses"""

    name = "courses"

    def ready(self):
        from courses import signals
