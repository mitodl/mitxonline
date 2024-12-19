``create_courseware``
=====================

Creates a new courseware object.

**For programs**, this creates the basic program record.
**For courses**, this creates the course, and then optionally adds it to the specified program (and can add it as an elective or required course). It will also optionally create an initial course run for the course. Finally, it will also add the course to the program's requirements or electives list.
**For courseruns**, this creates the course run and associates it with the specified course.

This will not run ``sync_course_run`` for you, so for best results, ensure the course run is set up on the edX side, use this command, then run ``sync_course_run`` to pull dates and other information from edX.

Syntax
------

``create_courseware <object> <readable id> <title> [--live] [--self-paced] [--create-run [create_run]] [--run-url [RUN_URL]] [--program [PROGRAM]] [--run-tag [run-tag]] [--required] [--elective] [--force] [--start <date>] [--end <date>] [--enrollment-start <date>] [--enrollment-end <date>] [--upgrade <date>] [--dept <department_name>] [--create-depts]``

Checks
------

The command performs the following checks:
* It checks to see if ``readable_id`` contains ``course`` or ``program`` at the front - if it doesn't, it will assume you've swapped the title and readable ID mistakenly and stop.
* It checks to see if the course will be live before adding it to the requirements tree. If ``--live`` isn't specified, it will ignore your request. This only applies to course creation.
* If creating a course or program, ``--depts`` must be specified and the department names must exist.

Both of these checks can be overridden with the ``--force`` flag.

Options
-------

* ``object`` - One of ``program``, ``course``, or ``courserun``
* ``readable id`` - The readable ID of the object. Note: do not specify the run tag for course runs.
* ``title`` - The title of the object.
* ``--live`` - Makes the object live (default is not).
* ``--force|-f`` - Force the creation of the object. (See "Checks" section for details.)
* ``--create-depts`` - If specified, any departments specified that do not currently exist will be created.

Programs can take the following options:
* ``--depts`` - The departments to associate the program with.

Courses can take the following options:

* ``--program <PROGRAM>`` - The program to assign the course to.
* ``--create-run <run tag>`` - Create a course run for this course with the specified run tag.
* ``--run-url <url>`` - The courseware URL for the course run. (Only if ``--create-run`` is specified.)
* ``--self-paced`` - The course run is self-paced. (Only if ``--create-run`` is specified.)
* ``--required`` - The course is a requirement for the program.
* ``--elective`` - The course is an elective for the program.
* ``--depts`` - The departments to associate the course with.

Course runs can take the following options:

* ``--program <PROGRAM>`` - The program to assign the course to. **Required.**
* ``--run-tag <run tag>`` - The run tag to use. **Required.**
* ``--run-url <url>`` - The courseware URL for the course run.
* ``--self-paced`` - The course run is self-paced.
* ``--start <date>`` - The date the course run should start.
* ``--end <date>`` - The date the course run should end.
* ``--enrollment-start <date>`` - The date the course run enrollment should start.
* ``--enrollment-end <date>`` - The date the course run enrollment should end.
* ``--upgrade <date>`` - The date after which course run enrollments should not be possible.
