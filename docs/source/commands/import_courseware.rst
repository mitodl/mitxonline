``import_courseware``
===============

Creates courserun(s) in the system based on edX course data.

You can specify either a specific courserun to create, or you can specify a run tag (e.g. ``1T2023``) and a program (e.g. ``program-v1:MITx+DEDP``), and the command will create courseruns for the courses that it finds in edX.

You can also optionally have it create a CMS page for the course, if one doesn't already exist.

The course itself must exist for this to work. No data in the course is updated. Any specified courserun that doesn't exist in edX will be skipped - it won't make empty course runs for you (use Django Admin or ``create_courseware`` if you want to do that, since you'll need to specify a few things that you can't here.) Similarly, any courserun that already exists will be skipped - ``sync_courserun``, which runs on a regular basis, will handle syncing the pertinent data for it.

New courseruns will be created with the following data synced from the edX course_details API call:
* Start and end dates
* Enrollment start and end dates
* Title
* Pacing (self-paced or instructor-led)
* Courseware URL (depends on the ``OPENEDX_API_BASE_URL`` configuration setting)

You may want to adjust these after they're created.

Syntax
------

``import_courseware [--courserun <courserun>] [--program <program> --run-tag <run tag>] [--live] [--create-cms-page]``

Options
-------

* ``--courserun <courserun>`` - The courserun to check for. Takes precedence over ``--program``.
* ``--program <program>`` - The program to look through. Requires ``--run_tag``. Specify either the numeric database ID or the readable ID for the program.
* ``--run-tag <run tag>`` - The run tag to use for the new courseruns. Required for ``--program``.
* ``--live`` - Make the course live. (Default is to set the flag to false.)
* ``--create-cms-page`` - Attempt to create a basic CMS page for the course, in a similar fashion to ``create_courseware_page``. If this fails (for instance, if the course already has a CMS page), this step will be skipped.

Example
-------

The use case for this was creating a batch of course runs for an upcoming semester of DEDP courses; these courses existed in edX but not in MITx Online. Since in that case the semester was 1T2023, this command would have created all the applicable courseruns all at once:

``manage.py import_courseware --program program-v1:MITx+DEDP --run-tag 1T2023 --live``
