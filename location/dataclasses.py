"""Dataclasses for the location app."""

from dataclasses import dataclass


@dataclass
class UserCalculatedLocation:
    """Describes how the user's location was determined."""

    country_code: str | None
    lookup_type: str
    ip: str


@dataclass(frozen=True)
class LocationFlagRule:
    """Describes how a LocationFlag determination rule is evaluated."""

    lookup_types: frozenset[str] | None
    match_all: bool
    require_all_types: bool = False
