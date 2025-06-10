"""Exception related classes and functions"""

from django.core.exceptions import ImproperlyConfigured

from rest_framework import exceptions, views


class EnvironmentVariableParseException(ImproperlyConfigured):
    """Environment variable was not parsed correctly"""


def exception_handler(exc, context):
    """Override DRF exception_handler to slightly change format of error response"""
    if isinstance(exc, exceptions.ValidationError) and isinstance(
        exc.detail, list | dict
    ):
        exc = exceptions.ValidationError(
            detail={"errors": exc.detail}, code=exc.status_code
        )
    return views.exception_handler(exc, context)
