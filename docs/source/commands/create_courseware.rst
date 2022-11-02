``create_courseware``
=====================

Creates a new courseware object. 

**For programs**, this creates the basic program record.
**For courses**, this creates the course, and then optionally adds it to the specified program. It will also optionally create an initial course run for the course. 
**For courseruns**, this creates the course run and associates it with the specified course.

This will not run ``sync_course_run`` for you, so for best results, ensure the course run is set up on the edX side, use this command, then run ``sync_course_run`` to pull dates and other information from edX. 

Syntax
------

``create_courseware <object> <readable id> <title> [--live] [--self-paced] [--create-run [create_run]] [--run-url [RUN_URL]] [--program [PROGRAM]] [--program-position [PROGRAM_POSITION]] [--run-tag [run-tag]]``

Options
-------

* ``object`` - One of ``program``, ``course``, or ``courserun``
* ``readable id`` - The readable ID of the object. Note: do not specify the run tag for course runs. 
* ``title`` - The title of the object.
* ``--live`` - Makes the object live (default is not).

Programs have no additional options (any specified will be ignored).

Courses can take the following options:

* ``--program <PROGRAM>`` - The program to assign the course to.
* ``--program-position <PROGRAM_POSITION>`` - The program position to set (default none).
* ``--create-run <run tag>`` - Create a course run for this course with the specified run tag. 
* ``--run-url <url>`` - The courseware URL for the course run. (Only if ``--create-run`` is specified.)
* ``--self-paced`` - The course run is self-paced. (Only if ``--create-run`` is specified.)

Course runs can take the following options:

* ``--program <PROGRAM>`` - The program to assign the course to. **Required.**
* ``--run-tag <run tag>`` - The run tag to use. **Required.**
* ``--program-position <PROGRAM_POSITION>`` - The program position to set (default none).
* ``--run-url <url>`` - The courseware URL for the course run.
* ``--self-paced`` - The course run is self-paced.

