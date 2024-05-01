``create_courseware_page``
==========================

Creates a very basic About page in the CMS for the given courseware object.

The about page will only have the handful of fields that are required to be there, and will be linked to the specified courseware object. If the courseware object is a course, it will also be added to the Featured Products section on the homepage. By default, the CMS page will be saved in a draft state.

Syntax
------

``create_courseware_page <courseware id> [--live]``

Options
-------

* ``courseware id`` - The courseware object to make a CMS page for.
* ``--live`` - Makes the resulting page live.
