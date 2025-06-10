import os

from django.core.exceptions import ImproperlyConfigured


class EnvironmentVariableParseException(ImproperlyConfigured):
    """Environment variable was not parsed correctly"""


def get_float(name, default):
    """
    Get an environment variable as an int.

    Args:
        name (str): An environment variable name
        default (float): The default value to use if the environment variable doesn't exist.

    Returns:
        float:
            The environment variable value parsed as an float
    """
    value = os.environ.get(name)
    if value is None:
        return default

    try:
        parsed_value = float(value)
    except ValueError as ex:
        msg = f"Expected value in {name}={value} to be a float"
        raise EnvironmentVariableParseException(msg) from ex

    return parsed_value
