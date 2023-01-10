import functools
from typing import Callable

from hubspot.crm.objects import ApiException

from hubspot_sync.exceptions import TooManyRequestsException


def raise_429() -> Callable:
    """
    Convert an ApiException to a TooManyRequestsException if status code is 429

     Returns:
         Callable: wrapped function (typically a celery task)
    """

    def task_run(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ApiException as ae:
                if int(ae.status) == 429:
                    raise TooManyRequestsException(ae)
                else:
                    raise

        return wrapper

    return task_run
