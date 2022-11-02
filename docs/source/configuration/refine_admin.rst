Refine Admin
############

Some administrative functionality is built out using `Refine <https://refine.dev>`_. The Refine admin is a separate application that uses OAuth2/OIDC for authentication and communicates with MITx Online via the standard REST API. It compliments the Django Admin interface, providing an interface for operations that would otherwise be hard to implement in Django Admin, and for users that don't necessarily need the level of access that Django Admin provides.

Accessing
*********

The Docker compose environment builds a ``refine`` container that runs a dev server available at port 8016. 

Set Up
======


Development
-----------


You will need to make some adjustments to the MITx Online configuration to allow the Refine admin to work.  

  Currently, the application expects to be accessible at ``mitxonline.odl.local``. 

Step 1: Generating the RSA Private Key for OIDC
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following command will generate the key:

``openssl genrsa 4096 2>/dev/null | sed -e 'H;${x;s/\n/\\n/g;s/^\\n//;p;};d'``

This will generate the key and then output it to the terminal in a format that can go into your ``.env`` file. Copy everything including the ``--BEGIN RSA PRIVATE KEY--`` and matching end part into a variable named ``OIDC_RSA_PRIVATE_KEY``. The key will need to be wrapped in quotes. Then, rebuild and restart your environment to pick up the changes. 

The key generation process is from the `Django OAuth Toolkit <https://django-oauth-toolkit.readthedocs.io/en/latest/oidc.html#creating-rsa-private-key>`_ docs.

Step 2: Configuring MITx Online
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You will need to add a new Application in the Django Oauth Toolkit section in Django Admin (``/admin/oauth2_provider/application/``). Navigate there and create a new Application. Use these values (overwriting the defaults where necessary):

* **Client Id**: ``refine-local-client-id``
* **Redirect uris**: ``http://mitxonline.odl.local:8013/staff-dashboard/oauth2/login/``
* **Client type**: Public
* **Authorization grants**: Authorization Code
* **Skip authorization**: checked
* **Algorithm**: RSA with SHA-2 256

It's also a good idea to provide a Name to differentiate it in the list. You don't need to have a Client Secret for this Application.

Take the Client Id and put it in the environment variable `MITX_ONLINE_REFINE_OIDC_CONFIG_CLIENT_ID`.

Once this has been saved, you should be able to log into the Refine admin successfully.

Deployments (RC, Production, etc)
---------------------------------


**Step 1: Generating the RSA Private Key for OIDC** 

The following command will generate the key:

``openssl genrsa 4096 2>/dev/null | sed -e 'H;${x;s/\n//g;s/^\\n//;p;};d'``

This will generate the key and then output it to the terminal. Copy everything including the ``--BEGIN RSA PRIVATE KEY--`` and matching end part into a variable named ``OIDC_RSA_PRIVATE_KEY``.

The key generation process is from the `Django OAuth Toolkit <https://django-oauth-toolkit.readthedocs.io/en/latest/oidc.html#creating-rsa-private-key>`_ docs.

**Step 2: Configuring MITx Online OAuth Provider** 

You will need to add a new Application in the Django OAuth Toolkit section in Django Admin (``/admin/oauth2_provider/application/``). Navigate there and create a new Application. Use these values (overwriting the defaults where necessary):

* **Redirect uris**: ``http://<hostname>/staff-dashboard/oauth2/login/``
* **Client type**: Public
* **Authorization grants**: Authorization Code
* **Skip authorization**: checked
* **Algorithm**: RSA with SHA-2 256

Take the Client Id and put it in the environment variable `MITX_ONLINE_REFINE_OIDC_CONFIG_CLIENT_ID`.

It's also a good idea to provide a Name to differentiate it in the list. You don't need to have a Client Secret for this Application.

Once this has been saved, you should be able to log into the Refine admin successfully.
