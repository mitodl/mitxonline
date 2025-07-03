def num_queries_from_course(course, version="v1"):
    """
    Generates approximately the number of queries we should expect to see, in a worst case scenario. This is
    difficult to predict without weighing down the test more as it traverses a bunch of wagtail and other related models.
    New endpoints should solve this, but the v1 endpoints will not change until/unless they are modified.

    programs see about 9 hits right now:
      -  4 are duplicated grabbing related courses
      -  3 grab flexible pricing data
      -  1 grabs content types related to it
      -  1 grabs the content of that content type

    course sees about 22 - this number varies on flexible pricing, wagtail data, and some relations with other objects
      - 12 are grabbing related objects both course objects and wagtail objects
      - 6 are grabbing flexible pricing
      - 4 are grabbing wagtail objects (page, image, etc)

    course runs grab about 6 (this varies if there's a relation to pricing)
      - ~4 are wagtail related - this is where things get hazy
      - 2 are checking relations

    Args:
        course (object): course object
        version (str): version string (v1, v2)
    """
    num_programs = len(course.programs)
    num_course_runs = course.courseruns.count()
    if version == "v1":
        return (9 * num_programs) + (num_course_runs * 6) + 20
    return num_programs + (num_course_runs * 6) + 20


def num_queries_from_programs(programs, version="v1"):
    """
    Program sees around 160+ queries per program. This is largely dependent on how much related data there is, but the
    fixture always generates the same (3 course runs per course, no more than 3 courses per program.

    The added on num_queries value is:
    - 4 query to get the program, related courses, related runs, department
    - 3 times num_courses for wagtail to get the generic data for the program and courses
    - 3 times num_courses for program requirements plus one for the initial call


    Args:
        programs (list): List of Program objects
        version (str): version string (v1, v2)
    """
    num_queries = 0
    for program in programs:
        required_courses = program.courses_qset
        num_courses = len(required_courses)
        if version == "v1":
            for course in required_courses:
                num_queries += num_queries_from_course(course)
            num_queries += 4 + (6 * num_courses) + 1
        if version == "v2":
            num_queries += 6 + (17 * num_courses) + 2
    return num_queries


def num_queries_from_department(num_departments, version="v2"):
    """
    v2 only as this was not in use prior
    each department gets a course query, a program query and there are 3 overall queries - s
        - site
        - department count
        - department IDs
    Args:
        num_departments (int): Number of department objects
        version (str): version string (v2)
    """
    return (num_departments * 2) + 3
