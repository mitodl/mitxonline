"""
Tests for courses api views v3
"""

import pytest
from django.db.models import Q
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.factories import ProgramEnrollmentFactory, ProgramFactory
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
            "enrollment_mode": program_enrollment.enrollment_mode,
        }
        for program_enrollment in program_enrollments
    ]


def test_create_program_enrollment(user_drf_client, user):
    """POST with a valid live program_id creates a new enrollment."""
    program = ProgramFactory.create(live=True)

    resp = user_drf_client.post(
        reverse("v3:user_program_enrollments_api-list"),
        data={"program_id": program.id},
        format="json",
    )

    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["program"]["readable_id"] == program.readable_id
    assert data["program"]["id"] == program.id
    assert data["enrollment_mode"] == "audit"
    assert data["certificate"] is None

    # Verify the enrollment exists in the DB
    assert ProgramEnrollment.objects.filter(
        user=user, program=program, active=True
    ).exists()


def test_create_program_enrollment_already_active(user_drf_client, user):
    """POST for a program the user is already enrolled in returns 200."""
    program = ProgramFactory.create(live=True)
    ProgramEnrollmentFactory.create(user=user, program=program)

    resp = user_drf_client.post(
        reverse("v3:user_program_enrollments_api-list"),
        data={"program_id": program.id},
        format="json",
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["program"]["readable_id"] == program.readable_id

    # No duplicate enrollment created
    assert ProgramEnrollment.objects.filter(user=user, program=program).count() == 1


def test_create_program_enrollment_reactivate(user_drf_client, user):
    """POST for a program with an inactive enrollment reactivates it and returns 201."""
    program = ProgramFactory.create(live=True)
    enrollment = ProgramEnrollmentFactory.create(
        user=user, program=program, active=False
    )
    enrollment.active = False
    enrollment.change_status = ENROLL_CHANGE_STATUS_UNENROLLED
    enrollment.save()

    resp = user_drf_client.post(
        reverse("v3:user_program_enrollments_api-list"),
        data={"program_id": program.id},
        format="json",
    )

    assert resp.status_code == status.HTTP_201_CREATED
    enrollment.refresh_from_db()
    assert enrollment.active is True


def test_create_program_enrollment_nonlive_program(user_drf_client):
    """POST with a non-live program returns 400."""
    program = ProgramFactory.create(live=False)

    resp = user_drf_client.post(
        reverse("v3:user_program_enrollments_api-list"),
        data={"program_id": program.id},
        format="json",
    )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_create_program_enrollment_not_found(user_drf_client):
    """POST with a nonexistent program_id returns 400."""
    resp = user_drf_client.post(
        reverse("v3:user_program_enrollments_api-list"),
        data={"program_id": 99999},
        format="json",
    )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_create_program_enrollment_unauthenticated():
    """POST without authentication returns 401 or 403."""
    program = ProgramFactory.create(live=True)
    client = APIClient()

    resp = client.post(
        reverse("v3:user_program_enrollments_api-list"),
        data={"program_id": program.id},
        format="json",
    )

    assert resp.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )
