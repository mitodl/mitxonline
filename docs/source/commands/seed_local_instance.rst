``seed_local_instance``
=======================

Seeds a local development instance without prompting, so it can run from automation (e.g. a ``kubectl exec`` with no TTY). It creates the same courseware as :doc:`configure_instance<configure_instance>`:

* The DEDP program (``program-v1:MITx+DEDP``), live, with a CMS page, a live financial assistance form, and financial assistance tiers.
* Demonstration Course (``course-v1:edX+DemoX``), a required course of DEDP, with the run ``course-v1:edX+DemoX+Demo_Course``.
* E2E Test Course (``course-v1:edX+E2E-101``) with the run ``course-v1:edX+E2E-101+course``.

Both courses are live and have CMS pages. Their runs are open now (dates are set automatically) and have a $999 product.

The program and each course are created only if nothing has their readable ID, so running the command again creates nothing. An existing program or course is skipped whole: its page, financial assistance form, run and product aren't checked or repaired. ``configure_tiers`` runs every time; it works on the current year's discounts, so in a new year it creates that year's discounts and expires the old ones.

The command only runs when ``MITX_ONLINE_ENVIRONMENT`` is ``local`` (ol-infrastructure local-dev) or ``dev`` (the default, e.g. docker compose). Deployed environments have the real DEDP program, and ``configure_tiers`` would replace its tiers.

The command expects migrations and ``configure_wagtail`` to have run. It doesn't create the edX OAuth2 application, the test learner, or anything in edX.

Syntax
------

``seed_local_instance [--superuser-email <email> --superuser-global-id <id>]``

Options
-------

* ``--superuser-email <email>`` - Make the user with this email a superuser. Requires ``--superuser-global-id``.
* ``--superuser-global-id <id>`` - The user's Keycloak ID. Requires ``--superuser-email``.

If no user has the global ID, the command creates one with it, using the email as the username. The API gateway backend looks users up by global ID, so the user's first login finds this row and fills in the rest. If a user has the global ID, that user is promoted, as long as its email matches (ignoring case).

The superuser step runs in its own transaction after the courseware is seeded. It stops with an error naming the user, and leaves the courseware in place, when:

* a user with that email or username has a different global ID (e.g. the Keycloak realm was recreated) or none (e.g. it was made by ``createsuperuser``)
* the user with the global ID has a different email
