"""
Tests for courses api views v3
"""

import pytest
from django.db.models import Q
from django.urls import reverse
from rest_framework import status

from courses.conftest import B2BCourses, UserWithEnrollmentsAndCerts
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    ProgramEnrollment,
)
from courses.serializers.v3.programs import SimpleProgramSerializer
from courses.test_utils import maybe_serialize_course_cert, maybe_serialize_program_cert

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True),
    pytest.mark.parametrize("course_catalog_program_count", [20], indirect=True),
    pytest.mark.usefixtures("b2b_courses", "course_catalog_data"),
]


def test_user_enrollments_detail(
    user_drf_client,
    user_with_enrollments_and_certificates: UserWithEnrollmentsAndCerts,
):
    """Test that user enrollments can be filtered by B2B organization ID"""
    enrollment = user_with_enrollments_and_certificates.run_enrollments[0]
    resp = user_drf_client.get(
        reverse("v3:user_enrollments_api-detail", kwargs={"pk": enrollment.id})
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {
        "id": enrollment.id,
        "run_id": enrollment.run.id,
        "course_id": enrollment.run.course_id,
        "b2b_contract_id": enrollment.run.b2b_contract_id,
        "b2b_organization_id": enrollment.run.b2b_contract.organization_id
        if enrollment.run.b2b_contract
        else None,
        "enrollment_mode": enrollment.enrollment_mode,
        "certificate": maybe_serialize_course_cert(enrollment.run, enrollment.user),
    }


def test_user_enrollments_list(
    user_drf_client,
    user_with_enrollments_and_certificates: UserWithEnrollmentsAndCerts,
):
    """Test that user enrollments can be filtered by B2B organization ID"""
    resp = user_drf_client.get(reverse("v3:user_enrollments_api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == [
        {
            "id": enrollment.id,
            "run_id": enrollment.run.id,
            "course_id": enrollment.run.course_id,
            "b2b_contract_id": enrollment.run.b2b_contract_id,
            "b2b_organization_id": enrollment.run.b2b_contract.organization_id
            if enrollment.run.b2b_contract
            else None,
            "enrollment_mode": enrollment.enrollment_mode,
            "certificate": maybe_serialize_course_cert(enrollment.run, enrollment.user),
        }
        for enrollment in user_with_enrollments_and_certificates.run_enrollments
    ]


def test_user_enrollments_list_filter_org_id(
    user_drf_client,
    b2b_courses: B2BCourses,
    user_with_enrollments_and_certificates: UserWithEnrollmentsAndCerts,
):
    """Test that user enrollments can be filtered by B2B organization ID"""
    org = b2b_courses.organizations[0]

    for org in b2b_courses.organizations:
        resp = user_drf_client.get(
            reverse("v3:user_enrollments_api-list"), {"org_id": org.id}
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == [
            {
                "id": enrollment.id,
                "run_id": enrollment.run.id,
                "course_id": enrollment.run.course_id,
                "b2b_contract_id": enrollment.run.b2b_contract_id,
                "b2b_organization_id": enrollment.run.b2b_contract.organization_id
                if enrollment.run.b2b_contract
                else None,
                "enrollment_mode": enrollment.enrollment_mode,
                "certificate": maybe_serialize_course_cert(
                    enrollment.run, enrollment.user
                ),
            }
            for enrollment in user_with_enrollments_and_certificates.run_enrollments
            if enrollment.run in b2b_courses.course_runs_by_org_id[org.id]
        ]

    resp = user_drf_client.get(
        reverse("v3:user_enrollments_api-list"), {"org_id": 99999}
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_user_enrollments_list_filter_exclude_b2b(
    user_drf_client,
    b2b_courses: B2BCourses,
    user_with_enrollments_and_certificates: UserWithEnrollmentsAndCerts,
):
    """Test that user enrollments can be filtered by B2B organization ID"""
    resp = user_drf_client.get(
        reverse("v3:user_enrollments_api-list"), {"exclude_b2b": True}
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == [
        {
            "id": enrollment.id,
            "run_id": enrollment.run.id,
            "course_id": enrollment.run.course_id,
            "b2b_contract_id": None,
            "b2b_organization_id": None,
            "enrollment_mode": enrollment.enrollment_mode,
            "certificate": maybe_serialize_course_cert(enrollment.run, enrollment.user),
        }
        for enrollment in user_with_enrollments_and_certificates.run_enrollments
        if enrollment.run not in b2b_courses.course_runs
    ]

    resp = user_drf_client.get(
        reverse("v3:user_enrollments_api-list"), {"exclude_b2b": False}
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == [
        {
            "id": enrollment.id,
            "run_id": enrollment.run.id,
            "course_id": enrollment.run.course_id,
            "b2b_contract_id": enrollment.run.b2b_contract_id,
            "b2b_organization_id": enrollment.run.b2b_contract.organization_id
            if enrollment.run.b2b_contract
            else None,
            "enrollment_mode": enrollment.enrollment_mode,
            "certificate": maybe_serialize_course_cert(enrollment.run, enrollment.user),
        }
        for enrollment in user_with_enrollments_and_certificates.run_enrollments
    ]


def test_program_enrollments(
    user_drf_client,
    user_with_enrollments_and_certificates,
    django_assert_max_num_queries,
):
    """
    Tests the program enrollments API, which should show the user's enrollment
    in programs with the course runs that apply.
    """
    user = user_with_enrollments_and_certificates.user

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
