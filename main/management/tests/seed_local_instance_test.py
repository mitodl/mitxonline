"""Tests for the seed_local_instance command"""

from io import StringIO

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError, call_command
from wagtail.models import Page

from cms.models import FlexiblePricingRequestForm
from courses.factories import ProgramFactory
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
def local_instance(settings):
    """Set up a local instance the way it is before seeding."""
    settings.ENVIRONMENT = "local"
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


@pytest.mark.parametrize("environment", ["local", "dev"])
def test_seed_courseware(settings, environment):
    """Without superuser options, only the courseware is seeded."""
    settings.ENVIRONMENT = environment

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


@pytest.mark.parametrize("stored_email", [EMAIL, EMAIL.title()])
def test_seed_superuser_promotes_existing_user(stored_email):
    """
    A user who already has the global_id is promoted, not recreated, when its
    email matches regardless of case.
    """
    existing = UserFactory.create(email=stored_email, global_id=GLOBAL_ID)

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


def test_seed_superuser_without_global_id():
    """A user with the email and no global_id gets its own message."""
    stale = UserFactory.create(email=EMAIL, global_id=None)

    with pytest.raises(CommandError) as exc:
        seed("--superuser-email", EMAIL, "--superuser-global-id", GLOBAL_ID)

    message = str(exc.value)
    assert f"User {stale.id} ({EMAIL}) has no global_id" in message
    assert "Keycloak realm" not in message
    assert "courseware is already seeded" in message
    assert_courseware_seeded()
    stale.refresh_from_db()
    assert stale.global_id is None
    assert not stale.is_superuser


def test_seed_superuser_global_id_of_another_user():
    """
    A global_id that belongs to a user with another email fails, and neither
    that user nor a user with the given email is promoted.
    """
    other = UserFactory.create(email="someone-else@example.com", global_id=GLOBAL_ID)
    stale = UserFactory.create(email=EMAIL, global_id=OLD_GLOBAL_ID)

    with pytest.raises(CommandError) as exc:
        seed("--superuser-email", EMAIL, "--superuser-global-id", GLOBAL_ID)

    message = str(exc.value)
    assert f"User {other.id} has global_id {GLOBAL_ID}" in message
    assert "someone-else@example.com" in message
    assert "courseware is already seeded" in message
    assert_courseware_seeded()
    for user in (other, stale):
        user.refresh_from_db()
        assert not user.is_superuser
        assert not user.is_staff


@pytest.mark.parametrize("environment", ["production", "rc", "ci", "pytest"])
def test_seed_refuses_outside_local_environments(settings, environment):
    """Outside local and dev, the command refuses before touching anything."""
    settings.ENVIRONMENT = environment
    program = ProgramFactory.create(readable_id=PROGRAM_ID)

    with pytest.raises(CommandError, match="only runs when MITX_ONLINE_ENVIRONMENT"):
        seed("--superuser-email", EMAIL, "--superuser-global-id", GLOBAL_ID)

    assert list(Program.objects.values_list("id", flat=True)) == [program.id]
    assert not Course.objects.exists()
    assert not FlexiblePriceTier.objects.exists()
    assert not Discount.objects.exists()
    assert not User.objects.exists()


@pytest.mark.parametrize(
    "args",
    [["--superuser-email", EMAIL], ["--superuser-global-id", GLOBAL_ID]],
)
def test_seed_superuser_options_together(args):
    """The superuser options must be given together, before anything is seeded."""
    with pytest.raises(CommandError, match="must be given together"):
        seed(*args)

    assert not Program.objects.exists()
