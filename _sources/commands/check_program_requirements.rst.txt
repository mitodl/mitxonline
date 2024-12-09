``check_program_requirements``
==============================

Checks programs for a valid requirements tree. A program has a valid requirements tree if it:

1. Exists
2. Has nodes for all courses assigned to the program

If the tree does not fit this criteria, an error message is printed to the screen. (This uses the ``check_program_for_orphans`` API call, but it suppresses its error logging so it won't clog up the error log.)

By default, this will check all programs in the system. Specify individual programs to check with ``--program`` (multiple times if needed) or check only live programs with ``--live``. Note that if you specify both of these together they will be combined: if you specify a check for a specific program that isn't live and then also specify ``--live``, it won't return anything for that program.

Syntax
------

``check_program_requirements [--program <readable or numeric id>] [--live]``

Options
-------

* ``--program <readable or numeric id>`` - Check this specific program. Can be either the readable ID of the program (e.g. ``program-v1:MITx+DEDP``) or the numeric ID, and can be specified multiple times to check multiple programs.
* ``--live`` - Check only live programs.
