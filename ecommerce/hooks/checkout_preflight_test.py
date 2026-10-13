"""Tests for the checkout pre-flight hookimpls."""

import pluggy
import pytest
from django.test import RequestFactory
from mitol.common.utils import now_in_utc

from ecommerce import hookspecs
from ecommerce.api import _run_checkout_preflight
from ecommerce.factories import (
    BasketFactory,
    BasketItemFactory,
    UnlimitedUseDiscountFactory,
)
from ecommerce.hooks.checkout_preflight import (
    CheckoutPreflight,
    _check_basket_discounts,
    _check_basket_finalized,
    _check_basket_purchasable,
    hookimpl,
)
from ecommerce.models import BasketDiscount
from main.constants import (
    USER_MSG_TYPE_BASKET_EMPTY,
    USER_MSG_TYPE_COURSE_NON_UPGRADABLE,
    USER_MSG_TYPE_DISCOUNT_INVALID,
    USER_MSG_TYPE_ENROLL_BLOCKED,
    USER_MSG_TYPE_ENROLL_DUPLICATED,
)
from main.plugin_manager import get_plugin_manager

pytestmark = pytest.mark.django_db


@pytest.fixture
def basket_request(user):
    """A basket with an item in it, and a request for its user."""

    basket = BasketFactory.create(user=user)
    BasketItemFactory.create(basket=basket)
    request = RequestFactory().get("/")
    request.user = user
    return request, basket


@pytest.mark.parametrize(
    ("failing", "expected"),
    [
        (None, None),
        (
            "has_user_blocked_products",
            {"country_blocked": True, "error": USER_MSG_TYPE_ENROLL_BLOCKED},
        ),
        (
            "has_user_purchased_same_courserun",
            {
                "purchased_same_courserun": True,
                "error": USER_MSG_TYPE_ENROLL_DUPLICATED,
            },
        ),
        (
            "has_user_purchased_non_upgradable_courserun",
            {
                "purchased_non_upgradeable_courserun": True,
                "error": USER_MSG_TYPE_COURSE_NON_UPGRADABLE,
            },
        ),
    ],
)
def test_check_basket_purchasable(mocker, basket_request, failing, expected):
    """Each failing purchasability check returns its own error payload."""

    request, basket = basket_request
    for check in (
        "has_user_blocked_products",
        "has_user_purchased_same_courserun",
        "has_user_purchased_non_upgradable_courserun",
    ):
        mocker.patch.object(basket, check, return_value=check == failing)

    assert _check_basket_purchasable(request, basket) == expected


@pytest.mark.parametrize("discounts_valid", [True, False])
def test_check_basket_discounts(mocker, basket_request, discounts_valid):
    """Invalid discounts get cleared and the user's discounts reapplied."""

    request, basket = basket_request
    mocker.patch(
        "ecommerce.api.check_basket_discounts_for_validity",
        return_value=discounts_valid,
    )
    mocked_apply = mocker.patch("ecommerce.api.apply_user_discounts")
    BasketDiscount.objects.create(
        redemption_date=now_in_utc(),
        redeemed_by=request.user,
        redeemed_discount=UnlimitedUseDiscountFactory.create(),
        redeemed_basket=basket,
    )

    result = _check_basket_discounts(request, basket)

    if discounts_valid:
        assert result is None
        mocked_apply.assert_not_called()
        assert basket.discounts.count() == 1
    else:
        assert result == {
            "invalid_discounts": True,
            "error": USER_MSG_TYPE_DISCOUNT_INVALID,
        }
        assert basket.discounts.count() == 0
        mocked_apply.assert_called_once_with(request)


@pytest.mark.parametrize("b2b_error", [{}, {"invalid_discounts": True, "error": "x"}])
@pytest.mark.parametrize("basket_empty", [True, False])
def test_check_basket_finalized(mocker, basket_request, b2b_error, basket_empty):
    """B2B validation errors win; otherwise an empty basket is an error."""

    request, basket = basket_request
    mocker.patch("ecommerce.api._validate_basket_steps_for_b2b", return_value=b2b_error)
    if basket_empty:
        basket.basket_items.all().delete()

    result = _check_basket_finalized(request, basket)

    if b2b_error:
        assert result == b2b_error
    elif basket_empty:
        assert result == {"basket_empty": True, "error": USER_MSG_TYPE_BASKET_EMPTY}
    else:
        assert result is None


def test_apply_contract_discounts(mocker, basket_request):
    """The apply step should pass the basket to the contract discount step."""

    request, basket = basket_request
    mocked_apply = mocker.patch("b2b.api.apply_contract_discounts_to_basket")

    CheckoutPreflight().apply_contract_discounts(request, basket)

    mocked_apply.assert_called_once_with(basket)


def test_checkout_preflight_registered():
    """The pre-flight hookimpls should be registered with the plugin manager."""

    pm = get_plugin_manager()

    assert any(isinstance(plugin, CheckoutPreflight) for plugin in pm.get_plugins())


class _Recorder:
    """Records the hooks that ran, and fails the one it's told to."""

    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def _record(self, name):
        self.calls.append(name)
        return {"error": name} if name == self.fail_at else None

    @hookimpl(specname="checkout_validate_basket")
    def validate_basket(self, request, basket):  # noqa: ARG002
        return self._record("validate_basket")

    @hookimpl(specname="checkout_apply_discounts")
    def apply_discounts(self, request, basket):  # noqa: ARG002
        self._record("apply_discounts")

    @hookimpl(specname="checkout_validate_discounts")
    def validate_discounts(self, request, basket):  # noqa: ARG002
        return self._record("validate_discounts")

    @hookimpl(specname="checkout_finalize_basket")
    def finalize_basket(self, request, basket):  # noqa: ARG002
        return self._record("finalize_basket")


ALL_STEPS = [
    "validate_basket",
    "apply_discounts",
    "validate_discounts",
    "finalize_basket",
]


@pytest.mark.parametrize(
    ("fail_at", "skip_discount_check", "expected_calls"),
    [
        (None, False, ALL_STEPS),
        (None, True, ["validate_basket", "finalize_basket"]),
        ("validate_basket", False, ["validate_basket"]),
        ("validate_discounts", False, ALL_STEPS[:3]),
        ("validate_discounts", True, ["validate_basket", "finalize_basket"]),
        ("finalize_basket", False, ALL_STEPS),
    ],
)
def test_run_checkout_preflight(
    mocker, basket_request, fail_at, skip_discount_check, expected_calls
):
    """
    The pre-flight steps run in order, stop at the first error, and skip the
    discount steps when asked to.
    """

    request, basket = basket_request
    recorder = _Recorder(fail_at=fail_at)
    pm = pluggy.PluginManager("mitxonline")
    pm.add_hookspecs(hookspecs)
    pm.register(recorder)
    mocker.patch("ecommerce.api.get_plugin_manager", return_value=pm)

    result = _run_checkout_preflight(
        request, basket, skip_discount_check=skip_discount_check
    )

    assert recorder.calls == expected_calls
    expected_error = fail_at if fail_at in expected_calls else None
    assert result == ({"error": expected_error} if expected_error else None)
