Configure Open edX
==================

In order to create user accounts in Open edX and permit authentication from MITx Online to Open edX, you need to configure MITx Online as an OAuth2 provider for Open edX.

Setup Open edX Devstack
#######################

Following steps are inspired by `edx-devstack <https://github.com/edx/devstack>`_.

Add ``/etc/hosts`` alias for Open edX
-------------------------------------

If one doesn't already exist, add an alias to ``/etc/hosts`` for Open edX. We have standardized this alias
to ``edx.odl.local``. Your ``/etc/hosts`` entry should look like this::

  127.0.0.1       edx.odl.local

Clone edx/devstack
------------------

.. code-block:: shell

  git clone https://github.com/edx/devstack
  cd devstack
  make requirements
  make dev.clone

Pull latest images and run provision
------------------------------------

.. code-block:: shell

  make pull
  make dev.provision


Start your servers
------------------

.. code-block:: shell

  make dev.up

Stop your servers
-----------------

.. code-block:: shell

  make stop

Setup social auth
#################

Install ``social-auth-mitxpro`` in LMS
--------------------------------------

There are two options for this:

Install via pip
^^^^^^^^^^^^^^^

.. code-block:: shell

    pip install social-auth-mitxpro

Install from local Build
^^^^^^^^^^^^^^^^^^^^^^^^

* Checkout the `social-auth-mitxpro <https://github.com/mitodl/social-auth-mitxpro>`_ project and build the package per the project instructions
* Copy the ``social-auth-mitxpro-$VERSION.tar.gz`` file into devstack's ``edx-platform`` directory
* In devstack, run ``make lms-shell`` and within that shell ``pip install social-auth-mitxpro-$VERSION.tar.gz``

  * To update to a new development version without having to actually bump the package version, simply ``pip uninstall social-auth-mitxpro``, then install again

Install ``mitxpro-openedx-extensions`` in LMS
---------------------------------------------

There are two options for this:

Install via pip
^^^^^^^^^^^^^^^

.. code-block:: shell

    pip install mitxpro-openedx-extensions

Install from local Build
^^^^^^^^^^^^^^^^^^^^^^^^

* Checkout the `mitxpro-openedx-extensions <https://github.com/mitodl/mitxpro-openedx-extensions>`_ project and build the package per the project instructions
* Copy the ``mitxpro-openedx-extensions-$VERSION.tar.gz`` file into devstack's ``edx-platform`` directory
* In devstack, run ``make lms-shell`` and within that shell ``pip install mitxpro-openedx-extensions-$VERSION.tar.gz``

  * To update to a new development version without having to actually bump the package version, simply ``pip uninstall -y mitxpro-openedx-extensions``, then install again

Configure MITx Online as a OAuth provider for Open edX
######################################################

In MITx Online:

* go to ``/admin/oauth2_provider/application/`` and create a new application with these settings selected:

  * ``Redirect uris``: ``http://<EDX_HOSTNAME>:18000/auth/complete/mitxpro-oauth2/``

    * **[macOS users]** You will need redirect uris for both the local edX host alias and for ``host.docker.internal``. This value should be::

        http://edx.odl.local:18000/auth/complete/mitxpro-oauth2/
        http://host.docker.internal:18000/auth/complete/mitxpro-oauth2/

    * **[Linux users]** You will need redirect uris for both the local edX host alias and for the gateway IP of the docker-compose networking setup for MITx Online as found via ``docker network inspect mitx-online_default``::

        http://edx.odl.local:18000/auth/complete/mitxpro-oauth2/
        http://<GATEWAY_IP>:18000/auth/complete/mitxpro-oauth2/

    * **[WSL 2 users]**: Use the URLs for macOS. You will also have to set ``OPENEDX_IP`` to ``host-gateway`` in your ``.env`` file to make this work. (Networking with WSL 2 works very differently, and the defaults won't work.)

    NOTE: ``GATEWAY_IP`` should be something like ``172.19.0.1``.

  * ``Client type``: "Confidential"
  * ``Authorization grant type``: "Authorization code"
  * ``Skip authorization``: checked
  * Other values are arbitrary but be sure to fill them all out. Save the client id and secret for later

In Open edX (derived from instructions `here <https://edx.readthedocs.io/projects/edx-installing-configuring-and-running/en/latest/configuration/tpa/tpa_integrate_open/tpa_oauth.html#additional-oauth2-providers-advanced>`_):

* ``make lms-shell`` into the LMS container and ensure the following settings:
    .. code-block:: yaml

      FEATURES:
        ALLOW_PUBLIC_ACCOUNT_CREATION: true
        ENABLE_COMBINED_LOGIN_REGISTRATION: true
        ENABLE_THIRD_PARTY_AUTH: true
        ENABLE_OAUTH2_PROVIDER: true
        SKIP_EMAIL_VALIDATION: true
      REGISTRATION_EXTRA_FIELDS:
        country: hidden
      THIRD_PARTY_AUTH_BACKENDS:
       - social_auth_mitxpro.backends.MITxProOAuth2

* ``make lms-restart`` to pick up the configuration changes
* Login to django-admin, go to ``http://<EDX_HOSTNAME>:18000/admin/third_party_auth/oauth2providerconfig/``, and create a new config:

  * Select the default example site
  * The slug field **MUST** match the the backend's name, which for us is ``mitxpro-oauth2``
  * Client Id should be the client id from the MITx Online Django Oauth Toolkit Application
  * Check the following checkboxes:

    * Skip hinted login dialog
    * Skip registration form
    * Sync learner profile data
    * Enable SSO id verification

  * In "Other settings", put:

    .. code-block:: json

      {
        "AUTHORIZATION_URL": "http://<LOCAL_MITX_ONLINE_ALIAS>:8013/oauth2/authorize/",
        "ACCESS_TOKEN_URL": "http://<EXTERNAL_MITX_ONLINE_HOST>:8013/oauth2/token/",
        "API_ROOT": "http://<EXTERNAL_MITX_ONLINE_HOST>:8013/"
      }

  * ``LOCAL_MITX_ONLINE_ALIAS`` should be your ``/etc/hosts`` alias for the mitxonline app
  * ``EXTERNAL_MITX_ONLINE_HOST`` will depend on your OS, but it needs to be resolvable within the edx container

    * Linux users: The gateway IP of the docker-compose networking setup for mitxonline as found via ``docker network inspect mitx-online_default``
    * OSX users: Use ``host.docker.internal``



Configure Open edX to support OAuth2 authentication from MITx Online
####################################################################

* In Open edX:

  * go to ``/admin/oauth2_provider/application/`` and verify that an application named 'edx-oauth-app' exists with these settings:

    * ``Redirect uris``: ``http://mitxonline.odl.local:8013/login/_private/complete``
    * ``Client type``: "Confidential"
    * ``Authorization grant type``: "Authorization code"
    * ``Skip authorization``: checked
    * Other values are arbitrary but be sure to fill them all out. Save the client id and secret for later

* In MITx Online:

  * Set ``OPENEDX_API_CLIENT_ID`` to the client id
  * Set ``OPENEDX_API_CLIENT_SECRET`` to the client secret

Configure Logout
################

* In Open edX, configure ``settings.IDA_LOGOUT_URI_LIST`` to be a list including the full url to ``<protocol>://<hostname>[:<port>]/logout`` in MITx Online

  * For devstack, this means modifying the value in ``edx-platform/lms/envs/devstack.py`` to include ``http://mitxonline.odl.local:8013/logout``
  * For production, this setting can go in ``lms.env.json`` under the key ``IDA_LOGOUT_URI_LIST`` as a JSON array of with that string in it

* MITx Online:

  * Set ``LOGOUT_REDIRECT_URL`` to the full path to the edx ``/logout`` view.

For local development this will be ``http://<EDX_HOSTNAME>:18000/logout``


Configure Open edX user and token for use with MITx Online management commands
##############################################################################

* In Open edX, create a staff user and then under ``/admin/oauth2_provider/accesstoken/`` add access token. The value of said token needs to match the value set for the ``OPENEDX_SERVICE_WORKER_API_TOKEN`` key in the MITx Online app.
