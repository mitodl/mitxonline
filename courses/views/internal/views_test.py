"""Tests for the internal views"""

import pytest
from django.urls import reverse
from faker import Faker
from rest_framework.test import APIClient

from courses.constants import (
    COURSE_VARIANT_INDUSTRY,
    COURSE_VARIANT_LANGUAGE,
    COURSE_VARIANT_LENGTH,
)
from courses.factories import CourseRunFactory
from courses.permissions import IsEtlUser
from users.factories import UserFactory

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True),
    pytest.mark.parametrize("course_catalog_program_count", [20], indirect=True),
    pytest.mark.usefixtures("b2b_courses", "course_catalog_data"),
]
fake = Faker()


@pytest.mark.parametrize(
    "is_etl",
    [
        False,
        True,
    ],
)
@pytest.mark.parametrize(
    "is_superuser",
    [
        False,
        True,
    ],
)
def test_is_etl_permission(rf, is_etl, is_superuser):
    """Test that the IsEtlUser permission class works as expected."""

    user = UserFactory.create(is_etl=is_etl, is_superuser=is_superuser)

    request = rf.get("/")
    request.user = user

    perm = IsEtlUser()

    assert perm.has_permission(request, {}) == (is_etl or is_superuser)


@pytest.mark.skip_nplusone_check
def test_get_ingestible_courses(b2b_courses):
    """Test that the ingestible courses endpoint returns data as expected."""

    user = UserFactory.create(is_etl=True)
    api_client = APIClient()
    api_client.force_authenticate(user)

    _, contracts_by_org_id, _, runs_by_contract, _ = b2b_courses

    contracts = [
        contract
        for org_id in contracts_by_org_id
        for contract in contracts_by_org_id[org_id]
    ]

    courses = []
    for contract in runs_by_contract:
        for run in runs_by_contract[contract]:
            if run.course not in courses:
                courses.append(run.course)

    variant_runs = []

    for course in courses:
        # Make some source runs, with variants.
        default_source = CourseRunFactory(
            course=course,
            is_source_run=True,
        )
        variant_source_1 = CourseRunFactory(
            course=course,
            is_source_run=True,
            is_primary_language=False,
            language=fake.random_element(COURSE_VARIANT_LANGUAGE)[0],
            variant_industry=fake.random_element(COURSE_VARIANT_INDUSTRY)[0],
            variant_length=fake.random_element(COURSE_VARIANT_LENGTH)[0],
        )
        variant_source_2 = CourseRunFactory(
            course=course,
            is_source_run=True,
            is_primary_language=False,
            language=fake.random_element(COURSE_VARIANT_LANGUAGE)[0],
            variant_industry=fake.random_element(COURSE_VARIANT_INDUSTRY)[0],
            variant_length=fake.random_element(COURSE_VARIANT_LENGTH)[0],
        )

        variant_runs.extend(
            [
                default_source.id,
                variant_source_1.id,
                variant_source_2.id,
            ]
        )

        # Make some public variants.
        variant_public_1 = CourseRunFactory(
            course=course,
            is_source_run=False,
            is_primary_language=False,
            language=variant_source_1.language,
            variant_industry=variant_source_1.variant_industry,
            variant_length=variant_source_1.variant_length,
        )
        variant_public_2 = CourseRunFactory(
            course=course,
            is_source_run=False,
            is_primary_language=False,
            language=variant_source_2.language,
            variant_industry=variant_source_2.variant_industry,
            variant_length=variant_source_2.variant_length,
        )

        variant_runs.extend(
            [
                variant_public_1.id,
                variant_public_2.id,
            ]
        )

        # Make some contract ones now.
        contract = fake.random_element(contracts)

        variant_contract_1 = CourseRunFactory(
            course=course,
            is_source_run=False,
            is_primary_language=False,
            language=variant_source_1.language,
            variant_industry=variant_source_1.variant_industry,
            variant_length=variant_source_1.variant_length,
            b2b_contract=contract,
        )
        variant_contract_2 = CourseRunFactory(
            course=course,
            is_source_run=False,
            is_primary_language=False,
            language=variant_source_2.language,
            variant_industry=variant_source_2.variant_industry,
            variant_length=variant_source_2.variant_length,
            b2b_contract=contract,
        )

        variant_runs.extend(
            [
                variant_contract_1.id,
                variant_contract_2.id,
            ]
        )

    params = {"page_size": 100}
    resp = api_client.get(reverse("internal_ingestible_courses-list"), params)

    assert resp.status_code == 200

    resp_json = resp.json()

    returned_run_ids = [
        courserun["id"]
        for course in resp_json["results"]
        for courserun in course["courseruns"]
    ]

    for variant_id in variant_runs:
        assert variant_id in returned_run_ids
