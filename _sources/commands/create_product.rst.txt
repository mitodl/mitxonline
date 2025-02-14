``create_product``
==================

Creates a product for the given courseware ID. (For now, this only works with course runs.)

By default, the product description will be the courseware ID. This is the recommended setting for this to make it easy to determine which products are for what courseware objects.

Syntax
------

``create_product <courserun> <price> [--description|-d <description>] [--inactive]``

Options
-------

* ``courserun`` - The course run to use.
* ``price`` - The price (numbers only) of the product.
* ``--description <description>`` (or ``-d``) - Optionally specify the product description. (Defaults to the courseware ID.)
* ``--inactive`` - Makes the product inactive. (Defaults to active.)
