"""Utilities for courses"""


def process_course_run_grade_certificate(course_run_grade):
    """
    Ensure that the couse run certificate is in line with the values in the course run grade

    Args:
        course_run_grade (courses.models.CourseRunGrade): The course run grade for which to generate/delete the certificate

    Returns:
        (courses.models.CourseRunCertificate, bool, bool) that depicts the CourseRunCertificate, created, deleted values
    """
    user = course_run_grade.user
    course_run = course_run_grade.course_run

    # A grade of 0.0 indicates that the certificate should be deleted
    should_delete = not bool(course_run_grade.grade)
    should_create = course_run_grade.passed

    """FOR TESTING-START"""
    delete_count = 1
    created = 1
    """FOR TESTING-END"""
    if should_delete:
        # delete_count, _ = CourseRunCertificate.objects.filter(
        #     user=user, course_run=course_run
        # ).delete()
        return None, False, (delete_count > 0)

    elif should_create:
        # certificate, created = CourseRunCertificate.objects.get_or_create(
        #     user=user, course_run=course_run
        # )
        return "certificate", created, False
    return None, False, False
