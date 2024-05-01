MITx Online Quick Start
=======================

You can use the ``configure_instance`` management command to perform a quick-start of a fresh MITx Online instance. This command takes care of a lot of the boilerplate required to set up an instance. It:

* Creates a superuser account (if you want)
* Creates the OAuth2 application record for edX (if you want, and optionally with an existing secret)
* Creates a set of courseware objects, including a DEDP program and courses with runs that match what ships with a standard devstack instance
* Creates a set of CMS pages for the courseware objects that it creates
* Sets up financial assistance appropriately
* Adds a couple of products in for the courses it creates
* Creates a learner account for the system

It does not:

* Run migrations
* Completely set up integration with devstack

In addition, there are a handful of tasks that you'll need to perform afterwards:

* The CMS pages (course about pages and the financial assistance form) need to be reviewed for content.
* The financial assistance form will need to be published, and linked into the appropriate course.
* You may want to adjust the products that are created.

The ``configure_instance`` command has a few flags you can use to customize how it works. For more details on this, either run it with ``--help`` or read the :doc:`configure_instance<../commands/configure_instance>` command documentation. (Do this especially if you're using the command to **reset** your MITx Online instance - you can provide an existing OAuth client ID and secret.)

Performing a Quick Start
------------------------

To quick-start your MITx Online instance:

1. Run the ``migrate`` command.
2. Run the ``createsuperuser`` command.
3. Follow the steps in the :doc:`Configure Open edX<open_edx>` documentation
4. Run ``configure_instance <platform>``, where ``platform`` is ``macos``, ``linux``, or ``none``. (If you don't want it to create OAuth2 records, set this to ``none`` or leave it blank. The default is ``none``.)

``configure_instance`` will prompt you to enter a password for the test learner account and will prompt you to enter account information for the superuser account. At the end, you'll see your edX OAuth2 application credentials, which can then be plugged into Open edX (if you haven't specified ``none`` for your platform).

Results
-------

Running ``configure_instance`` will peform these tasks in order:

1. Runs ``createsuperuser`` to create the superuser account (unless disabled with ``--dont-create-superuser``).
2. Creates the OAuth2 application record. (This is the one part of this that doesn't rely on an existing management command.)
3. Runs ``configure_wagtail`` to set up the CMS.
4. Runs ``configure_tiers`` to add the DEDP program and configure financial assistance tiers and discounts.
5. Runs ``create_courseware_page`` to add a basic about page for the DEDP program (required for the financial assistance form).
6. Runs ``create_finaid_form`` to create a financial assistance form for the DEDP program.
7. Runs ``create_courseware`` twice to create two courses, each with a course run, that correspond to the demo courses in devstack. (Details below.)
8. Runs ``sync_course_run`` to sync the courses with the devstack instance.
9. Runs ``create_product`` twice to create two products for the courses.
10. Runs ``create_courseware_page`` twice to add course pages for the two courses. (These are marked as live.)
11. Runs ``create_user`` to create the learner account.

The courses that are created are:

+----------------------+-----------------------+-------------+-------------+
| Course               | Readable ID           | Run Tag     | Price       |
+======================+=======================+=============+=============+
| Demonstration Course | course-v1:edX+DemoX   | Demo_Course | $999        |
+----------------------+-----------------------+-------------+-------------+
| E2E Test Course      | course-v1:edX+E2E-101 | course      | $999        |
+----------------------+-----------------------+-------------+-------------+

The learner account that is created is:

* Username: testlearner
* Email: testlearner@mitxonline.odl.local
* Display Name (split in half for first/last names): Test learner
* Country Code: US
* Enrollments: ``course-v1:edX+DemoX+Demo_Course``

The program that gets created is the standard DEDP program (``program-v1:MITx+DEDP``). The *Demonstration Course* is added to the DEDP program; *E2E Test Course* is not.

Notes
-----

The steps that involve communication with edX may not work if your environment isn't set up properly. In these cases, the attempts will be queued to be run later.

If you've set your platform to ``macos`` or ``linux``, the command will do the first part of the *Configure MITx Online as an OAuth provider for Open edX* section in the :doc:`Configure Open edX<open_edx>` documentation.
