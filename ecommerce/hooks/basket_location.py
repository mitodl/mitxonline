"""
Basket hook that records where the user is.

Runs before each basket change so the location is in place for anything
that needs it later in the change (tax, blocked-country checks).
"""

import logging

import pluggy

hookimpl = pluggy.HookimplMarker("mitxonline")
log = logging.getLogger(__name__)


class BasketLocation:
    """Geolocate the user and store the result on their basket."""

    @hookimpl
    def basket_pre_update(self, request, basket, update):  # noqa: ARG002
        """Determine the user's location and record it on the basket."""

        # location.api imports users.models, which pulls in ecommerce models;
        # import here to keep the plugin manager import light.
        from location.api import determine_user_location  # noqa: PLC0415

        # The location can't change within a request, so a request that adds
        # several products locates the basket once. Keyed by user too, since
        # claiming a basket gives it one (and so a profile to look at).
        located = request.__dict__.setdefault("_located_baskets", set())
        key = (basket.pk, request.user.pk)
        if key in located:
            return

        basket.set_location(determine_user_location(request))
        basket.save(update_fields=[*basket.LOCATION_FIELDS, "updated_on"])
        located.add(key)

        log.debug(
            "Basket %s located in %s (%s)",
            basket.id,
            basket.location_country_code or "unknown",
            basket.location_source,
        )
