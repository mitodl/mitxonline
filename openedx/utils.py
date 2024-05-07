"""Utility functions for the openedx app"""

from dataclasses import dataclass
from typing import Generic, List, TypeVar  # noqa: UP035
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

    created: List[T]  # noqa: UP006
    reactivated: List[T]  # noqa: UP006
    deactivated: List[T]  # noqa: UP006

    def __init__(
        self,
        created: List[T] = None,  # noqa: UP006, RUF013
        reactivated: List[T] = None,  # noqa: UP006, RUF013
        deactivated: List[T] = None,  # noqa: UP006, RUF013
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
