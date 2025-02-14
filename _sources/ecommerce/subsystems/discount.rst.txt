Discount Subsystem
==================

Discounts will need to be provided on occasion, these give the user a reduced price for some or all products. Treating this as a discount system and not necessarily a coupon system (e.g. a coupon is a kind of discount) is a good way to frame this approach.

The discount system would support discounts of multiple types. We’ve done discounts a lot of different ways before so we need to balance out flexibility against keeping complexity down. Each discount would be associated with a certain Product.

A discount may optionally be pre-associated with a User so that it can be automatically applied on checkout.

Discounts should only be computed on the backend, some of our ecommerce implementations have computed the discount on the frontend and we want to avoid this going forward.

Discount Types
^^^^^^^^^^^^^^
Discount types would track how the discounted price is computed, some examples/ideas:
``percent-off``: a percentage off the original price
``dollars-off``: a fixed dollar reduction in price (e.g. $30 off)
``fixed-price``: the price is discounted to the fixed price (e.g. a product would cost $100 regardless of what the original price was)

Redemption Types
^^^^^^^^^^^^^^^^
There may be a few different ways we want to track discount usage, for example:

``one-time``: the discount can only be used once by anyone
``one-time-per-user``: the discount can be used once per user
``unlimited``: the discount can be used any number of times

Data Models
^^^^^^^^^^^
.. code-block:: python

  class Discount(TimestampedModel):
      """Discount model"""
      amount = models.DecimalField(
          decimal_places=5,
          max_digits=20,
      )
      automatic = models.BooleanField(default=False)
      discount_type = models.CharField(
          choices=DISCOUNT_TYPES, max_length=30
      )
      redemption_type = models.CharField(
          choices=REDEMPTION_TYPES, max_length=30
      )
      max_redemptions = models.PositiveIntegerField(null=True)

  class UserDiscount(TimestampedModel):
      """pre-assignment for a discount to a user"""
      discount = models.ForeignKey(Discount)
      user = models.ForeignKey(User)

Implementation Proposal
^^^^^^^^^^^^^^^^^^^^^^^

Rather than codifying the discount logic in a complicated computation function, discount types can be implemented by abstracting the logic around discounts into a registry-driven discount factory like this:

.. code-block:: python

  import abc
  from dataclasses import dataclass


  @dataclass
  class DiscountType(abc.ABC):
      _CLASSES = {}

      discount: Discount

      # see https://www.python.org/dev/peps/pep-0487/
      def __init_subclass__(cls, *, discount_type, **kwargs):
          super().__init_subclass__(**kwargs)

          if discount_type in _CLASSES:
              raise TypeError(f"{discount_type} already defined for DiscountType")

          cls.discount_type = discount_type
          cls._CLASSES[discount_type] = cls

      @classmethod
      def for_discount(cls, discount: Discount):
          DiscountTypeCls = cls._CLASSES[discount.discount_type]

          return DiscountTypeCls(discount)

      def get_product_price(self, product: Product):
          return self.get_product_version_price(product.latest_version)

      @abc.abstractmethod
      def get_product_version_price(self, product_version: ProductVersion):
          ...

  class PercentDiscount(DiscountType, discount_type=Discount.PERCENT_DISCOUNT):

      def get_product_version_price(self, product_version: ProductVersion):
          return product_version.price * self.discount.amount

  class FixedPriceDiscount(DiscountType, discount_type=Discount.PERCENT_DISCOUNT):

      def get_product_version_price(self, product_version: ProductVersion):
          return self.discount.amount  # the amount here is the fixed price

With this implementation, prices before ordering would use get_product_price, whereas the receipt service would use get_product_version_price on the purchased versions. This makes it far more scalable to introduce new discount types without having to refactor existing code.
