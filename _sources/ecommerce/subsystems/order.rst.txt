Order Subsystem
===============

Orders represent a payment for some kind of product(s), these products will typically be either Programs or Course Runs. An order is marked as unfulfilled initially and then marked as fulfilled once a payment is completed. An order can fail or be refunded.

Data Model
^^^^^^^^^^
.. code-block:: python

  class Order(TimestampedModel):
      """An order containing information for a purchase."""
      status = models.CharField()
      purchaser = models.ForeignKey(settings.AUTH_USER_MODEL)
      total_price_paid = models.DecimalField()

  class Line(TimestampedModel):
      """A line in an Order."""

      order = models.ForeignKey(Order)
      product_version = models.ForeignKey(ProductVersion)
      quantity = models.PositiveIntegerField()

  class Transaction(TimestampedModel):
      """A transaction on an order, generally a payment but can also cover refunds"""
      order = models.ForeignKey(Order)
      amount = models.DecimalField(
          decimal_places=5,
          max_digits=20,
      )
      data = models.JSONField()
