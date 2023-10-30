import random

from courses.factories import (
    CourseFactory,
    CourseRunFactory,
    ProgramFactory,
    ProgramRequirementFactory,
)
from courses.models import (
    ProgramRequirementNodeType,
    ProgramRequirement,
)


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
        return (9 * num_programs) + (num_course_runs * 6) + 22
    return num_programs + (num_course_runs * 6) + 22


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
        required_courses = program.required_courses
        num_courses = len(required_courses)
        if version == "v1":
            for course in required_courses:
                num_queries += num_queries_from_course(course)
        num_queries += 4 + (6 * num_courses) + 1
    return num_queries


def populate_course_catalog_data(num_courses, num_programs):
    """
    Current production data is around 85 courses and 150 course runs. I opted to create 3 of each to allow
    the best course run logic to play out as well as to push the endpoint a little harder in testing.

    There are currently 3 programs in production, so I went with 15, again, to get ready for more data. To allow
    things to be somewhat random, I grab courses for them at random (one required and one elective) which also allows
    for courses to be in more than one program. If we need/want more specific test cases, we can add them, but this
    is a more robust data set than production is presently.

    Returns 3 separate lists to simulate what the tests received prior.

    Args:
        num_courses(int): number of courses to generate.
        num_programs(int): number of programs to generate.
    """
    programs = []
    courses = []
    course_runs = []
    for n in range(num_courses):
        course, course_runs_for_course = _create_course(n)
        courses.append(course)
        course_runs.append(course_runs_for_course)
    for n in range(num_programs):
        program = _create_program(courses)
        programs.append(program)
    return courses, programs, course_runs


def _create_course(n):
    test_course = CourseFactory.create(title=f"Test Course {n}")
    cr1 = CourseRunFactory.create(course=test_course, past_start=True)
    cr2 = CourseRunFactory.create(course=test_course, in_progress=True)
    cr3 = CourseRunFactory.create(course=test_course, in_future=True)
    return test_course, [cr1, cr2, cr3]


def _create_program(courses):
    program = ProgramFactory.create()
    ProgramRequirementFactory.add_root(program)
    root_node = program.requirements_root
    required_courses_node = root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )
    elective_courses_node = root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=2,
        title="Elective Courses",
        elective_flag=True,
    )
    if len(courses) > 3:
        for c in random.sample(courses, 3):
            required_courses_node.add_child(
                node_type=ProgramRequirementNodeType.COURSE, course=c
            )
        for c in random.sample(courses, 3):
            elective_courses_node.add_child(
                node_type=ProgramRequirementNodeType.COURSE, course=c
            )
    else:
        required_courses_node.add_child(
            node_type=ProgramRequirementNodeType.COURSE, course=courses[0]
        )
    return program
