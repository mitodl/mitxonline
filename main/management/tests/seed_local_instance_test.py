"""Tests for the seed_local_instance command"""

from io import StringIO

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError, call_command
from wagtail.models import Page

from cms.models import FlexiblePricingRequestForm
from courses.models import Course, CourseRun, Department, Program
from ecommerce.models import Discount, Product
from flexiblepricing.models import FlexiblePriceTier
from main.management.commands.seed_local_instance import PROGRAM_ID
from users.factories import UserFactory
from users.models import User

pytestmark = pytest.mark.django_db

EMAIL = "admin@example.com"
GLOBAL_ID = "8c6e1f0e-0d3a-4a43-9a8e-6f5e0bdb1a37"
OLD_GLOBAL_ID = "1b0f5a7d-54b3-4bd0-8d7e-2f8f6c0f3c11"
SEEDED_MODELS = [
    Program,
    Course,
    CourseRun,
    Department,
    Product,
    Discount,
    FlexiblePriceTier,
    Page,
    User,
]


@pytest.fixture(autouse=True)
def wagtail_site():
    """Set up Wagtail the way a local instance has it before seeding."""
    call_command("configure_wagtail")


def seed(*args):
    """Run the command, returning its output."""
    out = StringIO()
    call_command("seed_local_instance", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


def counts():
    """Count the rows of each model the command creates."""
    return {model.__name__: model.objects.count() for model in SEEDED_MODELS}


def assert_courseware_seeded():
    """Check that the program and courses exist as the command creates them."""
    program = Program.objects.get(readable_id=PROGRAM_ID)
    assert program.live
    assert program.page.live
    assert list(program.departments.values_list("name", flat=True)) == ["Economics"]
    assert (
        FlexiblePricingRequestForm.objects.descendant_of(program.page)
        .filter(live=True)
        .exists()
    )
    assert (
        FlexiblePriceTier.objects.filter(
            courseware_content_type=ContentType.objects.get_for_model(Program),
            courseware_object_id=program.id,
            current=True,
        ).count()
        == 4
    )

    for readable_id, run_id, department in [
        ("course-v1:edX+DemoX", "course-v1:edX+DemoX+Demo_Course", "Science"),
        ("course-v1:edX+E2E-101", "course-v1:edX+E2E-101+course", "Math"),
    ]:
        course = Course.objects.get(readable_id=readable_id)
        assert course.live
        assert course.page.live
        assert list(course.departments.values_list("name", flat=True)) == [department]
        run = CourseRun.objects.get(course=course)
        assert run.courseware_id == run_id
        assert run.is_enrollable
        assert [product.price for product in run.products.all()] == [999]

    assert [course.readable_id for course in program.required_courses] == [
        "course-v1:edX+DemoX"
    ]


def test_seed_courseware():
    """Without superuser options, only the courseware is seeded."""
    seed()

    assert_courseware_seeded()
    assert not User.objects.exists()


def test_seed_again_creates_nothing():
    """A second run finds everything and creates nothing."""
    seed("--superuser-email", EMAIL, "--superuser-global-id", GLOBAL_ID)
    seeded = counts()

    output = seed("--superuser-email", EMAIL, "--superuser-global-id", GLOBAL_ID)

    assert counts() == seeded
    assert f"Program {PROGRAM_ID} exists" in output
    assert "Course course-v1:edX+DemoX exists" in output
    assert "Course course-v1:edX+E2E-101 exists" in output
    assert "Created user" not in output


def test_seed_superuser():
    """The superuser is created with the given global_id."""
    output = seed("--superuser-email", EMAIL, "--superuser-global-id", GLOBAL_ID)

    user = User.objects.get(global_id=GLOBAL_ID)
    assert user.email == EMAIL
    assert user.username == EMAIL
    assert user.is_superuser
    assert user.is_staff
    assert f"Successfully promoted user {EMAIL} to superuser." in output


def test_seed_superuser_promotes_existing_user():
    """A user who already has the global_id is promoted, not recreated."""
    existing = UserFactory.create(email=EMAIL, global_id=GLOBAL_ID)

    seed("--superuser-email", EMAIL, "--superuser-global-id", GLOBAL_ID)

    assert list(User.objects.values_list("id", flat=True)) == [existing.id]
    existing.refresh_from_db()
    assert existing.is_superuser
    assert existing.is_staff


@pytest.mark.parametrize("match_on", ["email", "username"])
def test_seed_superuser_stale_global_id(match_on):
    """
    A user with the email or username but another global_id fails the
    superuser step and leaves the courseware.
    """
    stale = UserFactory.create(
        global_id=OLD_GLOBAL_ID,
        **(
            {"email": EMAIL.upper(), "username": "someone-else"}
            if match_on == "email"
            else {"email": "someone-else@example.com", "username": EMAIL}
        ),
    )

    with pytest.raises(CommandError) as exc:
        seed("--superuser-email", EMAIL, "--superuser-global-id", GLOBAL_ID)

    message = str(exc.value)
    assert f"User {stale.id} ({EMAIL})" in message
    assert OLD_GLOBAL_ID in message
    assert GLOBAL_ID in message
    assert "Keycloak realm was recreated" in message
    assert "courseware is already seeded" in message
    assert_courseware_seeded()
    assert list(User.objects.values_list("id", flat=True)) == [stale.id]
    stale.refresh_from_db()
    assert not stale.is_superuser


@pytest.mark.parametrize(
    "args",
    [["--superuser-email", EMAIL], ["--superuser-global-id", GLOBAL_ID]],
)
def test_seed_superuser_options_together(args):
    """The superuser options must be given together, before anything is seeded."""
    with pytest.raises(CommandError, match="must be given together"):
        seed(*args)

    assert not Program.objects.exists()
