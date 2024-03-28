``create_user``
===============

Creates a learner account in the system. You will be prompted for the account password. 

Syntax
------

``create_user username email firstname lastname displayname countrycode [--enroll <courseid>]``

Options
-------

* ``username`` - Username for the learner to create.
* ``email`` - Email address of the learner to create.
* ``firstname`` - The learner's first name.
* ``lastname`` - The learner's last name.
* ``displayname`` - The learner's display name.
* ``countrycode`` - The country code to use. (Default US)
* ``--enroll <courseid>`` - Optionally enroll the user in the specified course run. The enrollment will be an audit enrollment.