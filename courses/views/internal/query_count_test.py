"""Query-count regression tests for the internal ingestible-courses endpoint."""

import pytest
from django.urls import reverse
from faker import Faker
from rest_framework.test import APIClient
from rest_framework_api_key.models import APIKey

pytestmark = [pytest.mark.django_db]
fake = Faker()

# Ceiling for GET /api/internal/courses/. This is a per-request budget, not a
# per-course one: it must stay constant as the number of courses on the page
# grows. Tighten it as prefetches improve; never scale it by row count.
INGESTIBLE_COURSES_QUERY_BUDGET = 21


def _get_courses(client, page_size):
    _, key = APIKey.objects.create_key(name=str(fake.words(3)))
    return client.get(
        reverse("internal_ingestible_courses-list"),
        {"page_size": page_size},
        headers={"Authorization": f"Api-Key {key}"},
    )


@pytest.mark.usefixtures("course_catalog_data")
@pytest.mark.parametrize("course_catalog_program_count", [3], indirect=True)
@pytest.mark.parametrize("course_catalog_course_count", [1, 5, 20], indirect=True)
def test_ingestible_courses_query_count_is_flat_in_course_count(
    django_assert_max_num_queries, course_catalog_course_count
):
    """
    The ETL list endpoint's query count must not grow with the number of courses.

    This view serializes with IngestibleCourseWithCourseRunsSerializer, a
    CourseSerializer subclass, so it inherits every relation the v2 catalog
    serializer touches - course runs, topics, instructors, variants - and needs
    the matching prefetches. A constant bound that holds at 1, 5 and 20 courses
    is what actually pins those down.
    """
    client = APIClient()
    with django_assert_max_num_queries(INGESTIBLE_COURSES_QUERY_BUDGET):
        resp = _get_courses(client, page_size=100)

    assert resp.status_code == 200
    assert len(resp.json()["results"]) == course_catalog_course_count
