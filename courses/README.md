# xPRO: Programs, Program Runs, Courses, and Course Runs

**SECTIONS**
* [How to create a Program](#how-to-create-a-program)
* [How to create a Program Run](#how-to-create-a-program-run)
* [How to create a Course](#how-to-create-a-course)
* [How to create a Course Run](#how-to-create-a-course-run)

## How to create a Program

1. **Create a program** at: `/admin/courses/program/add/`
  - **Title**: the title of the program
  - **Readable id**: e.g. `program-v1:xPRO+SysEngx`
  - **Live**: check to make live


## How to create a Program Run

1. **[Create a Program](#how-to-create-a-program)** if necessary

2. **Create a program run**
  - If you're creating a new program or a complete set of course runs for a given program, you should create a new program run at `/admin/courses/programrun/add/`
  - **Program**: choose the correct program, e.g. `Architecture and Systems Engineering: Models and Methods to Manage Complex Systems`
  - **Run tag**: the run tag, e.g. `R11`
  - **Start date**: enter the start date for the earliest course in the program. Start time is `05:00:00` by convention.
  - **End date**: enter the end date for the latest course in the program. End time is `23:30:00` by convention.


## How to create a Course
1. **[Create a Program](#how-to-create-a-program)** if necessary

2. **[Create a Program Run](#how-to-create-a-program-run)** if necessary

3. **Create a new course** at: `/admin/courses/course/add/`
  - **Program**: if the course is a part of a program, select it from the pulldown
  - **Title**: the title of the course, e.g. `Leading Change in Organizations`
  - **Readable id**: the id, e.g. `course-v1:xPRO+LASERx3`
  - **Live**: Set to live when ready to launch. Note that you should not check this box for courses that will not need a catalog page, e.g. a SPOC or a private course.
  - **Departments**: select the applicable department(s)



## How to create a Course Run

The course team will announce on the xpro_newcourses moira list, after the course has been created in edX Studio. The announcement should include at minimum the course id. Pricing information will be provided by the marketing team, usiing the same moira list.

1. **[Create a Program](#how-to-create-a-program)** if necessary

2. **[Create a Program Run](#how-to-create-a-program-run)** if necessary

3. **[Create a Course](#how-to-create-a-course)** if necessary

4. **Create a course run** at `/admin/courses/courserun/add/`
  - **Course**: choose from the drop down
  - **Title**: should be the title of the course. Note this value should sync from xPRO Studio on a nightly basis. You can also use the management command `sync_courseruns` to do it immediately.
  - **Courseware id**: is the key for integration with open edX. It must be the same as the one used on xPRO Studiio, e.g. `course-v1:xPRO+SysEngx1+R4`
  - **Run tag**: should be the last component of the course id, e.g. `R4`
  - **Courseware url**: assuming this is an open edX course, the courseware path should be of the form
     `/courses/{course id}/course/`. Note that this path is not validated. (See
     https://github.com/mitodl/mitxpro/issues/1667)
  - all necessary dates will be pulled in automatically from xPRO Studio on a nightly basis. Or you can use the management command `sync_courseruns` to do it immediately.
  - **Live**: should be unchecked until you're ready to make the course run live. This value determines if the start date will appear in the list of options for the course page in the CMS.
  - **Save** and note the courserun id, you will need it later.
