"""Dataclasses for the ecommerce app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecommerce.models import BasketItem, Product


@dataclass
class BasketUpdate:
    """
    Describes a change to a basket, for the basket update hooks.

    Attributes:
    - operation (str): one of ecommerce.constants.BASKET_UPDATE_OPERATIONS
    - product (Product|None): the product being added, for item changes
    - basket_item (BasketItem|None): the item that changed; set only once the
      change is made, so it's None in basket_pre_update
    """

    operation: str
    product: Product | None = None
    basket_item: BasketItem | None = None
