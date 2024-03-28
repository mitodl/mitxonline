Product Subsystem
=================

The product subsystem is responsible for tracking all product-related data. Purchasable products are typically Programs and Course Runs. Pricing information is tracked as immutable data for the sake of historically accurate pricing for orders.

Data Models
^^^^^^^^^^^

.. code-block:: python

  @reversion.register(exclude=("content_type", "object_id", "created_on", "updated_on"))
  class Product(TimestampedModel):
      """
      Representation of a purchasable product. There is a GenericForeignKey to a Course or Program.
      """
      content_type = models.ForeignKey(ContentType)
      object_id = models.PositiveIntegerField()
      content_object = GenericForeignKey("content_type", "object_id")

This will utilize `django-reversion` to version product data.

APIs
^^^^

The API that would be primarily needed would be one to read back product data. It is presumed that data entry is done through django-admin:

- ``GET /api/v0/products/`` -> returns a paginated list of products
- ``GET /api/v0/products/1/`` -> returns a single product
