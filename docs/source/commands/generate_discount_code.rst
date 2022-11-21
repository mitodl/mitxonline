``generate_discount_code``
==========================

Creates discount code(s).

This can create a single code, a batch of explicitly defined codes, or a batch of automatically generated codes (with an optional prefix). 

Syntax
------

``generate_discount_code <code> [<code>...] --amount <amount> [-activates <date>] [--expires <date>] [--discount-type <discount type>] [--one-time] [--once-per-user] [--count <count>] [--prefix <prefix>]``

Batch Generating Codes
----------------------

You can create a batch of explicitly named codes by simply passing multiple discount codes to the command. All of the codes will be created (assuming they don't already exist) with the options you've specified. 

Alternatively, you can created a number of codes using the ``--count`` and ``-prefix`` option. Using these options will generate the number of codes specified by ``--count`` and will prefix the code with ``-prefix`` if it is specified. The code will be generated using a UUID - if you've supplied a prefix, the code will be in the format ``<prefix><uuid>``. Note that the command won't insert any punctuation between the prefix and the UUID, so you will need to add that yourself if you want, for example, a dash separating the two. UUIDs are 37 characters in length so prefixes need to be a total of 13 characters or less.

Output
------

Generated codes will be written to a ``generated-codes.csv`` file, with the following information:

* Discount code
* Code type
* Amount
* Expiration date

The file is overwritten if it exists. 

Options
-------

General options:

* ``--amount <amount>`` - The discount's amount. For percent off discounts, this should be on a scale of 0-100. This is required.
* ``--discount-type <discount type>`` - One of ``percent-off``, ``dollars-off``, or ``fixed-price``; the type of discount code to make. Defaults to ``percent-off``.
* ``--activates <date>`` - The date the code should become active (in ISO-8601 format).
* ``--expires <date>`` - The date the code should stop being active (in ISO-8601 format).
* ``--one-time`` - Set the discount to be redeemable only once. 
* ``--once-per-user`` - Set the discount to be redeemable only once per learner. 

For explicitly named codes:

* ``code`` - The code to generate. (You can specify any number of these.) Max length 50 characters.

For automatically generated codes:

* ``--count <count>`` - The number of codes to create.
* ``--prefix <prefix>`` - The prefix to append to the code. Max length 13 characters.
