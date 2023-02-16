``resolve_pending_order``
===============

Looks up the specified pending order in CyberSource and resolves it. This can mean either fulfilling the order or cancelling it, depending on the status of the payment in CyberSource: if the order is found and the result code is 100, it will be fulfilled; otherwise, it will be cancelled.

This only works on pending orders and won't accept a reference number for an order that's not in the Pending state.

Syntax
------

``resolve_pending_order [--all] [--order <reference number>]``

Options
-------

* ``--all`` - Process all pending orders.
* ``--order <reference number>`` - Process a specific order specified by reference number (e.g. ``mitxonline-prod-1``).
