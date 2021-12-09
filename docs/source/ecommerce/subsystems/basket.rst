Basket Subsystem
================

This tracks products intended to be purchased, often providing some additional state such as which runs under a program a user is purchasing.

A simple schema for this would be:

.. code-block:: python

  class Basket(TimestampedModel):
      """Represents a User's basket."""

      user = models.OneToOneField(settings.AUTH_USER_MODEL)

  class BasketItem(TimestampedModel):
      """Represents one or more products in a user's basket."""

      product = models.ForeignKey(Product)
      basket = models.ForeignKey(Basket)
      quantity = models.PositiveIntegerField()

APIs
^^^^

- ``GET  /api/v0/basket/`` -> get the current basket state
- ``POST /api/v0/basket/``  -> update the basket state

Notes
^^^^^
The implementation of this would use the discount subsystem to calculate the discounted prices, those values would be returned in the API for the frontend to use for display purposes.
