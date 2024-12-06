Payment Subsystem
=================

The payment subsystem takes unfulfilled orders, takes the user through payment completion, and finally marks the order as fulfilled. We historically and for the foreseeable future use CyberSource, but this should be strongly decoupled from the rest of the ecommerce system and made pluggable for future flexibility. This system would also be responsible for any webhooks/callbacks that the payment processor makes to us.
