``regenerate_edx_auth_tokens``
==================

Regenerates the authentication tokens for a specified learner. In essence, deletes the ``OpenEdxApiAuth`` record and then makes a call to edX to generate a new refresh and access token.

If the user doesn't have an ``OpenEdxUser`` record either, then this command is not appropriate. Use ``repair_missing_courseware_records`` instead. This will also not do anything with enrollments or grades. The main usecase is if the learner's ``OpenEdxApiAuth`` record gets deleted for some reason, or if their refresh tokens on the edX side are revoked.

Syntax
------

``regenerate_edx_auth_tokens <username>``

Options
-------

* ``username`` - the learner's ID, username, or email address.
