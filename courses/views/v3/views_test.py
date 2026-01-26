"""
Tests for courses api views v2
"""

import pytest
from django.db.models import Q
from django.urls import reverse
from rest_framework import status

from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    ProgramEnrollment,
)
from courses.serializers.v3.programs import SimpleProgramSerializer
from courses.test_utils import maybe_serialize_program_cert

pytestmark = [pytest.mark.django_db]


@pytest.mark.usefixtures("b2b_courses")
@pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [20], indirect=True)
def test_program_enrollments(
    user_drf_client,
    user_with_enrollments_and_certificates,
    django_assert_max_num_queries,
):
    """
    Tests the program enrollments API, which should show the user's enrollment
    in programs with the course runs that apply.
    """
    user = user_with_enrollments_and_certificates

    program_enrollments = (
        ProgramEnrollment.objects.filter(user=user)
        .filter(~Q(change_status=ENROLL_CHANGE_STATUS_UNENROLLED))
        .order_by("-id")
    )

    assert len(program_enrollments) > 0

    with django_assert_max_num_queries(4):
        resp = user_drf_client.get(reverse("v3:user_program_enrollments_api-list"))

    assert resp.status_code == status.HTTP_200_OK

    assert resp.json() == [
        {
            "program": SimpleProgramSerializer(
                instance=program_enrollment.program
            ).data,
            "certificate": maybe_serialize_program_cert(
                program_enrollment.program, user
            ),
        }
        for program_enrollment in program_enrollments
    ]
