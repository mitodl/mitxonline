``refund_fulfilled_order``
==========================

Looks up a fulfilled order in the system, sets it to Refunded, and then adjusts the enrollments accordingly. 

- If --unenroll is specified, the learner will be unenrolled from the course run associated with the order.
- If --audit is specified, the learner will keep their unenrollments, but they will be set to "audit" instead of "verified".

This does not make any sort of call to CyberSource or any other payment gateway to perform a refund - you're expected to have refunded the learner's money manually already. (At time of writing, PayPal transactions can't be refunded  using the normal means, so they get refunded manually via CyberSource and then  this command comes in to clean up afterwards.)

Syntax
------

``refund_fulfilled_order <reference number> [--audit] [--unenroll]``

Options
-------

* ``<reference number>`` - The reference number for the order to refund.
* ``--audit`` - Change the learner's enrollment status to ``audit``.
* ``--unenroll`` - Unenroll the learner.
