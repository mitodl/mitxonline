"""decorators for bootcamp-ecommerce"""
import functools
from typing import Callable, Optional

from django_redis import get_redis_connection
from hubspot.crm.objects import ApiException

from hubspot_sync.exceptions import TooManyRequestsException


def single_task(
    timeout: int,
    raise_block: Optional[bool] = True,
    key: Optional[str or Callable] = None,
    cache_name: Optional[str] = "redis",
) -> Callable:
    """
    Only allow one instance of a celery task to run concurrently
    Based on https://bit.ly/2RO2aav

    Args:
        timeout(int): Time in seconds to wait before relinquishing a lock
        raise_block(bool): If true, raise a BlockingIOError when locked
        key(str | Callable): Custom lock name or function to generate one
        cache_name(str): The name of the celery redis cache (default is "redis")

    Returns:
        Callable: wrapped function (typically a celery task)
    """

    def task_run(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            has_lock = False
            client = get_redis_connection(cache_name)
            if isinstance(key, str):
                lock_id = key
            elif callable(key):
                lock_id = key(func.__name__, args, kwargs)
            else:
                lock_id = func.__name__
            lock = client.lock(f"task-lock:{lock_id}", timeout=timeout)
            print(lock_id)
            try:
                has_lock = lock.acquire(blocking=False)
                if has_lock:
                    return_value = func(*args, **kwargs)
                else:
                    if raise_block:
                        raise BlockingIOError()
                    return_value = None
            finally:
                if has_lock and lock.locked():
                    lock.release()
            return return_value

        return wrapper

    return task_run


def raise_429(func) -> Callable:
    """
    Convert an ApiException to a TooManyRequestsException if status code is 429

     Returns:
         Callable: wrapped function (typically a celery task)
    """

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
