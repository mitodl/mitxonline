"""
Tests for course views
"""
# pylint: disable=unused-argument, redefined-outer-name, too-many-arguments
import operator as op

import pytest
import reversion
from django.db.models import Count, Q
from django.urls import reverse
from requests import ConnectionError as RequestsConnectionError
from requests import HTTPError
from rest_framework import status
from reversion.models import Version

from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.factories import (
    BlockedCountryFactory,
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
)
from courses.models import (
    CourseRun,
    ProgramEnrollment,
)
from courses.serializers.v1.courses import (
    CourseRunEnrollmentSerializer,
    CourseWithCourseRunsSerializer,
    CourseRunWithCourseSerializer,
)
from courses.serializers.v1.programs import ProgramSerializer
from courses.serializers.v1.courses import CourseRunSerializer
from courses.views.test_utils import (
    num_queries_from_course,
    num_queries_from_programs,
)
from courses.views.v1 import UserEnrollmentsApiViewSet
from ecommerce.factories import LineFactory, OrderFactory, ProductFactory
from ecommerce.models import Order
from fixtures.common import raise_nplusone
from main import features
from main.constants import (
    USER_MSG_COOKIE_NAME,
    USER_MSG_TYPE_ENROLL_BLOCKED,
    USER_MSG_TYPE_ENROLL_FAILED,
    USER_MSG_TYPE_ENROLLED,
)
from main.test_utils import assert_drf_json_equal, duplicate_queries_check
from main.utils import encode_json_cookie_value
from openedx.exceptions import NoEdxApiAuthError


pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("raise_nplusone")]


EXAMPLE_URL = "http://example.com"


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_get_programs(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles requests for all Programs"""
    _, programs, _ = course_catalog_data
    num_queries = num_queries_from_programs(programs, "v1")
    with django_assert_max_num_queries(num_queries) as context:
        resp = user_drf_client.get(reverse("v1:programs_api-list"))
    duplicate_queries_check(context)
    programs_data = sorted(resp.json(), key=op.itemgetter("id"))
    assert len(programs_data) == len(programs)
    for program, program_data in zip(programs, programs_data):
        assert_drf_json_equal(
            program_data, ProgramSerializer(program).data, ignore_order=True
        )


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_get_program(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles a request for single Program"""
    _, programs, _ = course_catalog_data
    program = programs[0]
    num_queries = num_queries_from_programs([program], "v1")
    with django_assert_max_num_queries(num_queries) as context:
        resp = user_drf_client.get(
            reverse("v1:programs_api-detail", kwargs={"pk": program.id})
        )
    duplicate_queries_check(context)
    program_data = resp.json()
    assert_drf_json_equal(
        program_data, ProgramSerializer(program).data, ignore_order=True
    )


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_create_program(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles a request to create a Program"""
    _, programs, _ = course_catalog_data
    program = programs[0]
    program_data = ProgramSerializer(program).data
    del program_data["id"]
    program_data["title"] = "New Program Title"
    request_url = reverse("v1:programs_api-list")
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.post(request_url, program_data)
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_patch_program(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles a request to patch a Program"""
    _, programs, _ = course_catalog_data
    program = programs[0]
    request_url = reverse("v1:programs_api-detail", kwargs={"pk": program.id})
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.patch(request_url, {"title": "New Program Title"})
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_delete_program(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles a request to delete a Program"""
    _, programs, _ = course_catalog_data
    program = programs[0]
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.delete(
            reverse("v1:programs_api-detail", kwargs={"pk": program.id})
        )
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [15], indirect=True)
def test_get_courses(
    user_drf_client, mock_context, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles requests for all Courses"""
    courses, _, _ = course_catalog_data
    courses_from_fixture = []
    num_queries = 0
    for course in courses:
        courses_from_fixture.append(
            CourseWithCourseRunsSerializer(instance=course, context=mock_context).data
        )
        num_queries += num_queries_from_course(course, "v1")
    with django_assert_max_num_queries(num_queries) as context:
        resp = user_drf_client.get(reverse("v1:courses_api-list"))
    #     This will become an assert rather than a warning in the future, for now this function is informational
    duplicate_queries_check(context)
    courses_data = resp.json()
    assert len(courses_data) == len(courses_from_fixture)
    """
    Due to the number of relations in our current course endpoint, and the potential for re-ordering of those nested
    objects, deepdiff has an ignore_order flag which I've added with an optional boolean argument to the assert_drf_json
    function.
    """
    assert_drf_json_equal(courses_data, courses_from_fixture, ignore_order=True)


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_get_course(
    user_drf_client,
    course_catalog_data,
    mock_context,
    django_assert_max_num_queries,
):
    """Test the view that handles a request for single Course"""
    courses, _, _ = course_catalog_data
    course = courses[0]
    num_queries = num_queries_from_course(course, "v1")
    with django_assert_max_num_queries(num_queries) as context:
        resp = user_drf_client.get(
            reverse("v1:courses_api-detail", kwargs={"pk": course.id})
        )
    duplicate_queries_check(context)
    course_data = resp.json()
    course_from_fixture = dict(
        CourseWithCourseRunsSerializer(instance=course, context=mock_context).data
    )
    assert_drf_json_equal(course_data, course_from_fixture, ignore_order=True)


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
@pytest.mark.parametrize("program_is_live", [True, False])
@pytest.mark.parametrize("program_page_is_live", [True, False])
def test_get_course_by_readable_id(
    user_drf_client,
    course_catalog_data,
    mock_context,
    django_assert_max_num_queries,
    program_is_live,
    program_page_is_live,
):
    """Test the view that handles a request for single Course"""
    courses, _, _ = course_catalog_data
    course = courses[0]

    if not program_is_live:
        course.programs[0].live = False
        course.programs[0].save()

    if not program_page_is_live:
        course.programs[0].page.live = False
        course.programs[0].page.save()

    num_queries = num_queries_from_course(course, "v1")
    with django_assert_max_num_queries(num_queries) as context:
        resp = user_drf_client.get(
            reverse("v1:courses_api-list"),
            {"readable_id": course.readable_id, "live": True},
        )
    duplicate_queries_check(context)
    course_data = resp.json()
    course_from_fixture = dict(
        CourseWithCourseRunsSerializer(
            instance=course,
            context={
                **mock_context,
                "all_runs": True,
            },
        ).data
    )
    assert_drf_json_equal(course_data, [course_from_fixture], ignore_order=True)

    if program_is_live and program_page_is_live:
        assert len(course_data[0]["programs"]) == 1
    else:
        assert course_data[0]["programs"] == []


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_create_course(
    user_drf_client,
    course_catalog_data,
    mock_context,
    django_assert_max_num_queries,
):
    """Test the view that handles a request to create a Course"""
    courses, _, _ = course_catalog_data
    course = courses[0]
    course_data = CourseWithCourseRunsSerializer(
        instance=course, context=mock_context
    ).data
    del course_data["id"]
    course_data["title"] = "New Course Title"
    request_url = reverse("v1:courses_api-list")
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.post(request_url, course_data)
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_patch_course(
    user_drf_client, course_catalog_data, django_assert_max_num_queries
):
    """Test the view that handles a request to patch a Course"""
    courses, _, _ = course_catalog_data
    course = courses[0]
    request_url = reverse("v1:courses_api-detail", kwargs={"pk": course.id})
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.patch(request_url, {"title": "New Course Title"})
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_delete_course(
    user_drf_client, course_catalog_data, django_assert_max_num_queries
):
    """Test the view that handles a request to delete a Course"""
    courses, _, _ = course_catalog_data
    course = courses[0]
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.delete(
            reverse("v1:courses_api-detail", kwargs={"pk": course.id})
        )
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_get_course_runs(user_drf_client, course_runs, django_assert_max_num_queries):
    """Test the view that handles requests for all CourseRuns"""
    with django_assert_max_num_queries(38) as context:
        resp = user_drf_client.get(reverse("v1:course_runs_api-list"))
    duplicate_queries_check(context)
    course_runs_data = resp.json()
    assert len(course_runs_data) == len(course_runs)
    # Force sorting by run id since this test has been flaky
    course_runs_data = sorted(course_runs_data, key=op.itemgetter("id"))
    for course_run, course_run_data in zip(course_runs, course_runs_data):
        assert course_run_data == CourseRunWithCourseSerializer(course_run).data


@pytest.mark.parametrize("is_enrolled", [True, False])
def test_get_course_runs_relevant(
    mocker,
    user_drf_client,
    course_runs,
    user,
    is_enrolled,
    django_assert_max_num_queries,
):
    """A GET request for course runs with a `relevant_to` parameter should return user-relevant course runs"""
    course_run = course_runs[0]
    user_enrollments = Count(
        "enrollments",
        filter=Q(
            enrollments__user=user,
            enrollments__active=True,
            enrollments__edx_enrolled=True,
        ),
    )
    patched_run_qset = mocker.patch(
        "courses.views.v1.get_user_relevant_course_run_qset",
        return_value=CourseRun.objects.filter(id=course_run.id)
        .annotate(user_enrollments=user_enrollments)
        .order_by("-user_enrollments", "enrollment_start"),
    )

    if is_enrolled:
        CourseRunEnrollmentFactory.create(user=user, run=course_run, edx_enrolled=True)

    with django_assert_max_num_queries(20) as context:
        resp = user_drf_client.get(
            f"{reverse('v1:course_runs_api-list')}?relevant_to={course_run.course.readable_id}"
        )
    duplicate_queries_check(context)
    patched_run_qset.assert_called_once_with(course_run.course, user)
    course_run_data = resp.json()[0]

    assert course_run_data["is_enrolled"] == is_enrolled


def test_get_course_runs_relevant_missing(
    user_drf_client, django_assert_max_num_queries
):
    """A GET request for course runs with an invalid `relevant_to` query parameter should return empty results"""
    with django_assert_max_num_queries(3) as context:
        resp = user_drf_client.get(
            f"{reverse('v1:course_runs_api-list')}?relevant_to=invalid+course+id"
        )
    duplicate_queries_check(context)
    course_runs_data = resp.json()
    assert course_runs_data == []


def test_get_course_run(user_drf_client, course_runs, django_assert_max_num_queries):
    """Test the view that handles a request for single CourseRun"""
    course_run = course_runs[0]
    with django_assert_max_num_queries(18) as context:
        resp = user_drf_client.get(
            reverse("v1:course_runs_api-detail", kwargs={"pk": course_run.id})
        )
    duplicate_queries_check(context)
    course_run_data = resp.json()
    assert course_run_data == CourseRunWithCourseSerializer(course_run).data


def test_create_course_run(user_drf_client, course_runs, django_assert_max_num_queries):
    """Test the view that handles a request to create a CourseRun"""
    course_run = course_runs[0]
    course_run_data = CourseRunSerializer(course_run).data
    del course_run_data["id"]
    course_run_data.update(
        {
            "title": "New CourseRun Title",
            "courseware_id": "new-courserun-id",
            "courseware_url_path": "http://example.com",
        }
    )
    request_url = reverse("v1:course_runs_api-list")
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.post(request_url, course_run_data)
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_patch_course_run(user_drf_client, course_runs, django_assert_max_num_queries):
    """Test the view that handles a request to patch a CourseRun"""
    course_run = course_runs[0]
    request_url = reverse("v1:course_runs_api-detail", kwargs={"pk": course_run.id})
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.patch(request_url, {"title": "New CourseRun Title"})
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_delete_course_run(user_drf_client, course_runs, django_assert_max_num_queries):
    """Test the view does not handle a request to delete a CourseRun"""
    course_run = course_runs[0]
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.delete(
            reverse("v1:course_runs_api-detail", kwargs={"pk": course_run.id})
        )
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_user_enrollments_list(user_drf_client, user):
    """The user enrollments view should return serialized enrollments for the logged-in user"""
    assert UserEnrollmentsApiViewSet.serializer_class == CourseRunEnrollmentSerializer
    user_run_enrollment = CourseRunEnrollmentFactory.create(user=user)
    resp = user_drf_client.get(reverse("v1:user-enrollments-api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert_drf_json_equal(
        resp.json(),
        [
            CourseRunEnrollmentSerializer(
                user_run_enrollment, context={"include_page_fields": True}
            ).data
        ],
    )


@pytest.mark.parametrize("sync_dashboard_flag", [True, False])
def test_user_enrollments_list_sync(
    mocker, settings, user_drf_client, user, sync_dashboard_flag
):
    """
    If the appropriate feature flag is turned on, the enrollments list API call should sync enrollments with
    """
    settings.FEATURES[features.SYNC_ON_DASHBOARD_LOAD] = sync_dashboard_flag
    patched_sync = mocker.patch(
        "courses.views.v1.sync_enrollments_with_edx",
    )
    resp = user_drf_client.get(reverse("v1:user-enrollments-api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert patched_sync.called is sync_dashboard_flag
    if sync_dashboard_flag is True:
        patched_sync.assert_called_once_with(user)


@pytest.mark.parametrize("exception_raised", [NoEdxApiAuthError, HTTPError, ValueError])
def test_user_enrollments_list_sync_fail(
    mocker, settings, user_drf_client, user, exception_raised
):
    """
    The enrollments list API should log an exception and continue if enrollment syncing fails for any reason
    """
    settings.FEATURES[features.SYNC_ON_DASHBOARD_LOAD] = True
    patched_sync = mocker.patch(
        "courses.views.v1.sync_enrollments_with_edx", side_effect=exception_raised
    )
    patched_log_exception = mocker.patch("courses.views.v1.log.exception")
    resp = user_drf_client.get(reverse("v1:user-enrollments-api-list"))
    assert resp.status_code == status.HTTP_200_OK
    patched_sync.assert_called_once()
    patched_log_exception.assert_called_once()


@pytest.mark.parametrize("ignore_failures_flag", [True, False])
def test_user_enrollments_create(
    mocker, settings, user_drf_client, user, ignore_failures_flag
):
    """The user enrollments view should succeed when creating a new enrollment"""
    settings.FEATURES[features.IGNORE_EDX_FAILURES] = ignore_failures_flag
    course = CourseFactory.create()
    run = CourseRunFactory.create(course=course)
    fake_enrollment = CourseRunEnrollmentFactory.create(run=run)
    patched_enroll = mocker.patch(
        "courses.serializers.v1.courses.create_run_enrollments",
        return_value=([fake_enrollment], True),
    )
    resp = user_drf_client.post(
        reverse("v1:user-enrollments-api-list"), data={"run_id": run.id}, many=True
    )
    assert resp.status_code == status.HTTP_201_CREATED
    patched_enroll.assert_called_once_with(
        user,
        [run],
        keep_failed_enrollments=ignore_failures_flag,
    )
    # Running a request to create the enrollment again should succeed
    resp = user_drf_client.post(
        reverse("v1:user-enrollments-api-list"), data={"run_id": run.id}
    )
    assert resp.status_code == status.HTTP_201_CREATED


def test_user_enrollments_create_invalid(user_drf_client, user):
    """The user enrollments view should fail when creating a new enrollment with an invalid run id"""
    resp = user_drf_client.post(
        reverse("v1:user-enrollments-api-list"), data={"run_id": 1234}
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.json() == {"errors": {"run_id": f"Invalid course run id: 1234"}}


@pytest.mark.parametrize(
    "deactivate_fail, exp_success, exp_status_code",
    [
        [False, True, status.HTTP_204_NO_CONTENT],
        [True, False, status.HTTP_400_BAD_REQUEST],
    ],
)
def test_user_enrollment_delete(
    mocker,
    settings,
    user_drf_client,
    user,
    deactivate_fail,
    exp_success,
    exp_status_code,
):
    """
    The user enrollment view DELETE handler should unenroll in edX and deactivate the local enrollment record, and
    return the appropriate status code depending on the success of the unenrollment.
    """
    settings.FEATURES[features.IGNORE_EDX_FAILURES] = False
    enrollment = CourseRunEnrollmentFactory.create(
        user=user, active=True, change_status=None
    )
    inactive_enrollment = CourseRunEnrollmentFactory.create(
        user=user,
        active=False,
        change_status=ENROLL_CHANGE_STATUS_UNENROLLED,
        edx_emails_subscription=False,
    )
    patched_deactivate = mocker.patch(
        "courses.views.v1.deactivate_run_enrollment",
        return_value=(None if deactivate_fail else inactive_enrollment),
    )
    resp = user_drf_client.delete(
        reverse("v1:user-enrollments-api-detail", kwargs={"pk": enrollment.id})
    )
    patched_deactivate.assert_called_once_with(
        enrollment,
        change_status=ENROLL_CHANGE_STATUS_UNENROLLED,
        keep_failed_enrollments=False,
    )
    assert resp.status_code == exp_status_code
    final_enrollment = patched_deactivate.return_value
    assert final_enrollment == None if deactivate_fail else inactive_enrollment
    if not deactivate_fail:
        assert final_enrollment.edx_emails_subscription is False


def test_user_enrollment_delete_other_fail(mocker, settings, user_drf_client, user):
    """
    The user enrollment view DELETE handler should reject a request to deactivate another user's enrollment
    """
    other_user_enrollment = CourseRunEnrollmentFactory.create(
        user__username="other-user", active=True, change_status=None
    )
    patched_deactivate = mocker.patch("courses.views.v1.deactivate_run_enrollment")
    resp = user_drf_client.delete(
        reverse(
            "v1:user-enrollments-api-detail", kwargs={"pk": other_user_enrollment.id}
        )
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    patched_deactivate.assert_not_called()


@pytest.mark.parametrize("api_request", [True, False])
@pytest.mark.parametrize("product_exists", [True, False])
def test_create_enrollments(mocker, user_client, api_request, product_exists):
    """
    Create enrollment view should create an enrollment and include a user message in the response cookies.
    Unless api_request is set to True, in which case we should get a string back.
    """
    patched_create_enrollments = mocker.patch(
        "courses.views.v1.create_run_enrollments",
        return_value=(None, True),
    )
    mock_fulfilled_order_filter = mocker.patch(
        "ecommerce.models.FulfilledOrder.objects.filter", return_value=None
    )
    run = CourseRunFactory.create()
    if product_exists:
        with reversion.create_revision():
            product = ProductFactory.create(purchasable_object=run)
    resp = user_client.post(
        reverse("create-enrollment-via-form"),
        data={"run": str(run.id), "isapi": "true"}
        if api_request
        else {"run": str(run.id)},
    )

    if api_request:
        assert "Ok" in str(resp.content)
        if product_exists:
            assert Order.objects.filter(state=Order.STATE.PENDING).count() == 1
        else:
            assert Order.objects.filter(state=Order.STATE.PENDING).count() == 0
    else:
        assert resp.status_code == status.HTTP_302_FOUND
        assert resp.url == reverse("user-dashboard")
        assert USER_MSG_COOKIE_NAME in resp.cookies
        assert resp.cookies[USER_MSG_COOKIE_NAME].value == encode_json_cookie_value(
            {
                "type": USER_MSG_TYPE_ENROLLED,
                "run": run.title,
            }
        )
    patched_create_enrollments.assert_called_once()


def test_create_enrollments_failed(mocker, settings, user_client):
    """
    Create enrollment view should redirect and include a user message in the response cookies if the enrollment
    request to edX fails
    """
    settings.FEATURES[features.IGNORE_EDX_FAILURES] = False
    patched_create_enrollments = mocker.patch(
        "courses.views.v1.create_run_enrollments",
        return_value=(None, False),
    )
    run = CourseRunFactory.create()
    resp = user_client.post(
        reverse("create-enrollment-via-form"),
        data={"run": str(run.id)},
        HTTP_REFERER=EXAMPLE_URL,
    )
    assert resp.status_code == status.HTTP_302_FOUND
    assert resp.url == EXAMPLE_URL
    assert USER_MSG_COOKIE_NAME in resp.cookies
    assert resp.cookies[USER_MSG_COOKIE_NAME].value == encode_json_cookie_value(
        {
            "type": USER_MSG_TYPE_ENROLL_FAILED,
        }
    )
    patched_create_enrollments.assert_called_once()


def test_create_enrollments_no_run(mocker, user_client):
    """Create enrollment view should redirect if the run doesn't exist"""
    patched_log_error = mocker.patch("courses.views.v1.log.error")
    resp = user_client.post(
        reverse("create-enrollment-via-form"),
        data={"run": "1234"},
        HTTP_REFERER=EXAMPLE_URL,
    )
    assert resp.status_code == status.HTTP_302_FOUND
    patched_log_error.assert_called_once()
    assert resp.url == EXAMPLE_URL


def test_create_enrollments_blocked_country(user_client, user):
    """
    Create enrollment view should redirect with a user message in a cookie if the attempted enrollment is blocked
    """
    run = CourseRunFactory.create()
    BlockedCountryFactory.create(course=run.course, country=user.legal_address.country)
    resp = user_client.post(
        reverse("create-enrollment-via-form"),
        data={"run": str(run.id)},
        HTTP_REFERER=EXAMPLE_URL,
    )
    assert resp.status_code == status.HTTP_302_FOUND
    assert resp.url == EXAMPLE_URL
    assert USER_MSG_COOKIE_NAME in resp.cookies
    assert resp.cookies[USER_MSG_COOKIE_NAME].value == encode_json_cookie_value(
        {
            "type": USER_MSG_TYPE_ENROLL_BLOCKED,
        }
    )


@pytest.mark.parametrize("receive_emails", [True, False])
def test_update_user_enrollment(mocker, user_drf_client, user, receive_emails):
    """the enrollment should update the course email subscriptions"""
    run_enrollment = CourseRunEnrollmentFactory.create(user=user)
    fake_enrollment = {"fake": "enrollment"}
    patch_func = (
        "subscribe_to_edx_course_emails"
        if receive_emails
        else "unsubscribe_from_edx_course_emails"
    )
    patched_email_subscription = mocker.patch(
        f"courses.views.v1.{patch_func}", return_value=fake_enrollment
    )
    resp = user_drf_client.patch(
        reverse("v1:user-enrollments-api-detail", kwargs={"pk": run_enrollment.id}),
        data={"receive_emails": "on" if receive_emails else ""},
    )
    assert resp.status_code == status.HTTP_200_OK
    patched_email_subscription.assert_called_once_with(user, run_enrollment.run)


@pytest.mark.parametrize("receive_emails", [True, False])
@pytest.mark.parametrize(
    "exception_raised", [NoEdxApiAuthError, HTTPError, RequestsConnectionError]
)
def test_update_user_enrollment_failure(
    mocker, user_drf_client, user, receive_emails, exception_raised
):
    """the enrollment update failure to the course email subscriptions"""
    run_enrollment = CourseRunEnrollmentFactory.create(user=user)
    patch_func = (
        "subscribe_to_edx_course_emails"
        if receive_emails
        else "unsubscribe_from_edx_course_emails"
    )
    patched_email_subscription = mocker.patch(
        f"courses.views.v1.{patch_func}", side_effect=exception_raised
    )
    patched_log_exception = mocker.patch("courses.views.v1.log.exception")
    resp = user_drf_client.patch(
        reverse("v1:user-enrollments-api-detail", kwargs={"pk": run_enrollment.id}),
        data={"receive_emails": "on" if receive_emails else ""},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    patched_email_subscription.assert_called_once_with(user, run_enrollment.run)
    patched_log_exception.assert_called_once()


def test_program_enrollments(user_drf_client, user, programs):
    """
    Tests the program enrollments API, which should show the user's enrollment
    in programs with the course runs that apply.
    """

    enrollments = []
    for program in programs:
        enrollment = ProgramEnrollment(user=user, program=program)
        enrollment.save()
        enrollments.append(enrollment)

    course = CourseFactory.create()
    programs[1].add_requirement(course)
    course_run = CourseRunFactory.create(course=course)
    course_run_enrollment = CourseRunEnrollmentFactory.create(run=course_run, user=user)

    resp = user_drf_client.get(reverse("v1:user_program_enrollments_api-list"))

    assert resp.status_code == status.HTTP_200_OK

    resp_data = resp.json()

    assert len(resp_data) == len(programs)

    for program_detail in resp_data:
        if program_detail["program"]["id"] == programs[1].id:
            assert program_detail["enrollments"][0]["id"] == course_run_enrollment.id
        else:
            assert len(program_detail["enrollments"]) == 0


@pytest.mark.parametrize("fulfilled_order_exists", [True, False])
def test_create_enrollments_with_existing_fulfilled_order(
    mocker, user_client, user, fulfilled_order_exists
):
    """
    Create enrollment view should not create a new PendingOrder if a FulFilledOrder containing the same Line's
    and related to the user already exists.  This can occur when a user pays for a verified enrollment, but the
    verified enrollment mode is no synced with Edx, and then the user attempts to enroll into the course a second
    time.
    """
    patched_create_enrollments = mocker.patch(
        "courses.views.v1.create_run_enrollments",
        return_value=(None, True),
    )
    run = CourseRunFactory.create()
    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=run)
    if fulfilled_order_exists:
        order = OrderFactory.create(state=Order.STATE.FULFILLED, purchaser=user)
        version = Version.objects.get_for_object(product).first()
        LineFactory.create(order=order, purchased_object=run, product_version=version)
    resp = user_client.post(
        reverse("create-enrollment-via-form"),
        data={"run": str(run.id), "isapi": "true"},
    )

    assert "Ok" in str(resp.content)
    if fulfilled_order_exists:
        assert Order.objects.filter(state=Order.STATE.PENDING).count() == 0
    else:
        assert Order.objects.filter(state=Order.STATE.PENDING).count() == 1
    patched_create_enrollments.assert_called_once()
