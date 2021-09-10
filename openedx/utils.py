"""Utility functions for the openedx app"""
from dataclasses import dataclass
from typing import NamedTuple, TypeVar, List, Generic
from urllib.parse import urljoin

from django.conf import settings


def edx_url(path):
    """Returns the full url to the provided path"""
    return urljoin(settings.OPENEDX_API_BASE_URL, path)


def edx_redirect_url(path):
    """Returns the full url to the provided path using the edX hostname specified for redirects"""
    return urljoin(settings.OPENEDX_BASE_REDIRECT_URL, path)


T = TypeVar("T")


@dataclass
class SyncResult(Generic[T]):
    """Represents the results of a sync with edX"""

    created: List[T]
    reactivated: List[T]
    deactivated: List[T]

    def __init__(
        self,
        created: List[T] = None,
        reactivated: List[T] = None,
        deactivated: List[T] = None,
    ):
        self.created = created or []
        self.reactivated = reactivated or []
        self.deactivated = deactivated or []

    @property
    def no_changes(self):
        """Returns True if this sync object does not indicate any changes"""
        return all(
            [
                len(self.created) == 0,
                len(self.reactivated) == 0,
                len(self.deactivated) == 0,
            ]
        )
