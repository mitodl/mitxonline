``configure_instance``
======================

Configures a fresh MITx Online instance. For more information, see :doc:`MITx Online Quick Start<../configuration/quickstart>` and :doc:`Local Open edX Tutor and MITx Online Deployment<../configuration/tutor>`.

For Tutor deployments, this will use ``local.edly.io`` for URLs for the edX platform. If you're running a dev deployment, or are using Tutor Nightly, ``--tutor-dev`` will additionally add the proper ports (as Caddy is disabled in these cases). In either case, the two demo courses will still be created but only the Demonstration Course (``course-v1:edX+DemoX+Demo_Course``) will exist in edX, and then only if you import the demo course using the relevant Tutor command.

Syntax
------

``configure_instance <platform> [--dont-enroll|-D] [--dont-create-superuser|-S] [--edx-oauth-client <client id>] [--edx-oauth-secret <client secret>] [--gateway <ip>] [--tutor|-T] [--tutor-dev]``

Options
-------

* ``<platform>`` - One of ``macos``, ``linux``, or ``none``. Specifying ``none`` will additionaly stop creation of the OAuth2 application record for edX. Defaults to ``none``.
* ``--dont-enroll|-D`` - Don't enroll the test learner account in any courses. (Defaults to enrolling the account in ``course-v1:edX+DemoX+Demo_Course``.)
* ``--dont-create-superuser|-S`` - Don't create a superuser account.
* ``--gateway <ip>`` - The Docker gateway IP. Required on Linux. See :doc:`Configure Open edX<../configuration/open_edx>` for more info.
* ``--edx-oauth-client <client id>`` - Use the specified client ID for the edX OAuth2 client. (Useful if you're redoing your MITx Online instance and you've already created the corresponding record in edX, since you're not allowed to edit it there.)
* ``--edx-oauth-secret <client secret>`` - Use the specified client secret for the edX OAuth2 client. (Useful if you're redoing your MITx Online instance and you've already created the corresponding record in edX, since you're not allowed to edit it there.)
* ``--tutor|-T`` - Configure the instance for use with a Tutor edX deployment.
* ``--tutor-dev`` - Configure the instnace for use with Tutor dev or nightly.
