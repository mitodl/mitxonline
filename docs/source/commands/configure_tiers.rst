``configure_tiers``
===================

Creates financial assistance tiers and discounts for a course or program.

This operates in two modes: creating tiers for a program and creating tiers for a course.

*In the tables below, <year> represents the current year.*

**Configuring tiers for a course** 

The command will use the readable ID of the course as part of the financial aid discounts. They will default to this:

=========================== ============= ======
Code                        Type          Amount
=========================== ============= ======
<course id>-fa-tier1-<year> percent-off   .75
<course id>-fa-tier2-<year> percent-off   .50
<course id>-fa-tier3-<year> percent-off   .25
<course id>-fa-tier4-<year> percent-off   0
=========================== ============= ======

Note that configuring course tiers requires the course to exist. Use ``create_courseware`` (or any of the other methods) to create the course before you run this command.

**Configuring tiers for a program**

The command will create or reuse a program. By default, the program it will try to use is:

* Data, Econonmics and Development Policy
* program-v1:MITx+DEDP
* Abbreviated to DEDP

The default discounts will be:

==================== =========== ======
Code                 Type        Amount
==================== =========== ======
DEDP-fa-tier1-<year> dollars-off 750
DEDP-fa-tier2-<year> dollars-off 650
DEDP-fa-tier3-<year> dollars-off 500
DEDP-fa-tier4-<year> percent-off 0
==================== =========== ======

Specify changes using ``--program``, ``--program-name``, and/or ``--program-abbrev``. 

**Tiers**

The actual tiers that will be created are:

========= ========================
Threshold Discount
========= ========================
$0        <abbrev>-fa-tier1-<year>
$25,000   <abbrev>-fa-tier2-<year>
$50,000   <abbrev>-fa-tier3-<year>
$75,000   <abbrev>-fa-tier4-<year>
========= ========================

These can be overridden by providing a CSV file. The CSV file should have the following fields and should not have a header row::

  threshold amount,discount type,discount amount

If you specify tier information, you must provide all the tiers you want to create - the specified information will override the default. In addition, you must supply a zero income tier. This is a requirement and the command will quit if you don't have one set up, as that tier is used as the starting point for financial assistance. (In other words, learners will see errors if there's not a zero-income threshold tier set up.)

**Reuse**

The command will try to reuse any discounts and tiers that match ones the command would have created, so you can safely run this for a course or program that may have already had financial assistance tiers set up.

Syntax
------

Configuring tiers for a program:
``configure_tiers [--program <readable id>] [--program-name <name of the program>] [--program-abbrev <program abbreviation>] [--tier-info <tier info CSV>]``

Configuring tiers for a course:
``configure_tiers [--course <readable id>] [--tier-info <tier info CSV>]``

Options
-------

Program options:

* ``--program <readable id>`` - Program ID to use or create. Defaults to ``program-v1:MITx+DEDP``.
* ``--program-name <name of the program>`` - Name of the new program. Defaults to ``Data, Economics and Development Policy``.
* ``--program-abbrev <abbreviation>`` - Abbreviation to use for tiers and discounts. Defaults to ``DEDP``. 

Course options:

* ``--course <readable id>`` - Course ID to use. This won't create a course; use ``create_courseware`` for that. 

Common options:

* ``--tier-info <csv file>`` - Tier info in CSV format.
