"""Dataclasses for the location app."""

from dataclasses import dataclass


@dataclass
class UserCalculatedLocation:
    """Describes how the user's location was determined."""

    country_code: str | None
    lookup_type: str
    ip: str
