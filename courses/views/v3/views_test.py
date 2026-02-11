"""
Tests for courses api views v2
"""

import pytest
from django.db.models import Q
from django.urls import reverse
from rest_framework import status

from b2b.factories import ContractPageFactory, OrganizationPageFactory
from courses.conftest import CourseCatalogData, UserWithEnrollmentsAndCerts
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
)
from courses.models import (
    ProgramEnrollment,
)
from courses.serializers.v3.programs import SimpleProgramSerializer
from courses.test_utils import maybe_serialize_program_cert

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [20], indirect=True)
def test_user_enrollments_b2b_organization(
    b2b_courses: B2BCourses,
    course_catalog_data: CourseCatalogData,
    user_with_enrollments_and_certificates: UserWithEnrollmentsAndCerts,
):
    """Test that user enrollments can be filtered by B2B organization ID"""

    org = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=org)

    regular_course = CourseFactory.create()
    regular_run = CourseRunFactory.create(course=regular_course)

    b2b_course = CourseFactory.create()
    b2b_run = CourseRunFactory.create(course=b2b_course, b2b_contract=contract)

    CourseRunEnrollmentFactory.create(user=user, run=regular_run)
    b2b_enrollment = CourseRunEnrollmentFactory.create(user=user, run=b2b_run)

    resp = user_drf_client.get(reverse("v2:user-enrollments-api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 2

    resp = user_drf_client.get(
        reverse("v2:user-enrollments-api-list"), {"org_id": org.id}
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == b2b_enrollment.id
    assert data[0]["b2b_organization_id"] == org.id
    assert data[0]["b2b_contract_id"] == contract.id

    resp = user_drf_client.get(
        reverse("v2:user-enrollments-api-list"), {"org_id": 99999}
    )
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 0


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
