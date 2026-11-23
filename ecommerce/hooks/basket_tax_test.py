"""Tests for the basket tax hook."""

import pytest

from ecommerce.constants import BASKET_UPDATE_ADD_ITEM
from ecommerce.dataclasses import BasketUpdate
from ecommerce.factories import BasketFactory
from ecommerce.hooks.basket_tax import BasketTax

pytestmark = pytest.mark.django_db


def test_basket_tax_hook(mocker, user):
    """The hook recalculates the basket's tax."""

    mock_recalc = mocker.patch("ecommerce.api.recalculate_basket_tax")
    basket = BasketFactory.create(user=user)

    BasketTax().basket_post_update(
        request=None,
        basket=basket,
        update=BasketUpdate(operation=BASKET_UPDATE_ADD_ITEM),
    )

    mock_recalc.assert_called_once_with(basket)
