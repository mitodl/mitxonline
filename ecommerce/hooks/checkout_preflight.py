"""
Checkout pre-flight hooks.

These are the checks generate_checkout_payload runs before it creates an
order. Each check that fails returns the error payload that checkout hands
back to the caller.

ecommerce.api is imported inside the hooks: it imports ecommerce.models, which
imports the plugin manager, which imports this module.
"""

import pluggy

from main.constants import (
    USER_MSG_TYPE_BASKET_EMPTY,
    USER_MSG_TYPE_COURSE_NON_UPGRADABLE,
    USER_MSG_TYPE_DISCOUNT_INVALID,
    USER_MSG_TYPE_ENROLL_BLOCKED,
    USER_MSG_TYPE_ENROLL_DUPLICATED,
)

hookimpl = pluggy.HookimplMarker("mitxonline")


def _check_basket_purchasable(request, basket) -> dict | None:
    """Check that the user is allowed to buy what's in the basket."""

    if basket.has_user_blocked_products(request.user):
        return {
            "country_blocked": True,
            "error": USER_MSG_TYPE_ENROLL_BLOCKED,
        }

    if basket.has_user_purchased_same_courserun(request.user):
        return {
            "purchased_same_courserun": True,
            "error": USER_MSG_TYPE_ENROLL_DUPLICATED,
        }

    if basket.has_user_purchased_non_upgradable_courserun():
        return {
            "purchased_non_upgradeable_courserun": True,
            "error": USER_MSG_TYPE_COURSE_NON_UPGRADABLE,
        }

    return None


def _check_basket_discounts(request, basket) -> dict | None:
    """
    Check that the basket's discounts are still valid.

    If they aren't, clear them and reapply the ones the user should get, so
    the user can see the corrected price before they try again.
    """

    from ecommerce.api import (  # noqa: PLC0415
        apply_user_discounts,
        check_basket_discounts_for_validity,
    )

    if check_basket_discounts_for_validity(request):
        return None

    # We only allow one discount per basket so clear all of them here.
    basket.discounts.all().delete()
    apply_user_discounts(request)
    return {
        "invalid_discounts": True,
        "error": USER_MSG_TYPE_DISCOUNT_INVALID,
    }


def _check_basket_finalized(request, basket) -> dict | None:
    """Check the basket against its contracts, and that it isn't empty."""

    from ecommerce.api import _validate_basket_steps_for_b2b  # noqa: PLC0415

    b2b_validation_result = _validate_basket_steps_for_b2b(basket, request)

    if b2b_validation_result:
        return b2b_validation_result

    if not basket.basket_items.count():
        return {
            "basket_empty": True,
            "error": USER_MSG_TYPE_BASKET_EMPTY,
        }

    return None


class CheckoutPreflight:
    """The core checkout pre-flight checks."""

    @hookimpl(specname="checkout_validate_basket")
    def check_basket_purchasable(self, request, basket) -> dict | None:
        """Call the internal function (so we can test it)"""

        return _check_basket_purchasable(request, basket)

    @hookimpl(specname="checkout_apply_discounts")
    def apply_contract_discounts(self, request, basket) -> None:  # noqa: ARG002
        """Pick up contract pricing for items in the user's contracts."""

        from b2b.api import apply_contract_discounts_to_basket  # noqa: PLC0415

        apply_contract_discounts_to_basket(basket)

    @hookimpl(specname="checkout_validate_discounts")
    def check_basket_discounts(self, request, basket) -> dict | None:
        """Call the internal function (so we can test it)"""

        return _check_basket_discounts(request, basket)

    @hookimpl(specname="checkout_finalize_basket")
    def check_basket_finalized(self, request, basket) -> dict | None:
        """Call the internal function (so we can test it)"""

        return _check_basket_finalized(request, basket)
