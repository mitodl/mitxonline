"""
Seeds a local development instance of MITx Online without prompting.

This creates the same courseware as configure_instance:
- The DEDP program (program-v1:MITx+DEDP), live, with a CMS page, a live
  financial assistance form and financial assistance tiers.
- Demonstration Course (course-v1:edX+DemoX), a required course of DEDP, with
  the run course-v1:edX+DemoX+Demo_Course.
- E2E Test Course (course-v1:edX+E2E-101) with the run
  course-v1:edX+E2E-101+course.
Both courses are live, have CMS pages, and their runs are open now (dates are
set automatically) with a $999 product.

With --superuser-email and --superuser-global-id, it also makes that user a
superuser. The user is created with the given global_id (the Keycloak user ID)
if no user has it, so that the user's first login through the API gateway
finds this row: the gateway backend looks users up by global_id, and a row
without it would collide with the login on email.

Each object is created only if it's missing, so running this again creates
nothing. (configure_tiers works on the current year's discounts, so in a new
year it creates that year's discounts and expires the old ones.) The
courseware and the superuser are separate transactions; if the superuser step
fails, the courseware stays.

This expects migrations and configure_wagtail to have run. It doesn't create
the edX OAuth2 application, the test learner, or anything in edX; use
configure_instance for those.
"""

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction
from django.db.models import Q

from courses.models import Course, Program

PROGRAM_ID = "program-v1:MITx+DEDP"
PROGRAM_TITLE = "Data, Economics and Development Policy"
PROGRAM_DEPARTMENT = "Economics"
COURSE_PRICE = 999

# readable ID, title, run tag, department, required course of the program
COURSES = [
    ("course-v1:edX+DemoX", "Demonstration Course", "Demo_Course", "Science", True),
    ("course-v1:edX+E2E-101", "E2E Test Course", "course", "Math", False),
]


class Command(BaseCommand):
    """
    Seeds a local development instance of MITx Online.
    """

    help = "Seeds a local MITx Online instance with the DEDP program, two courses, and optionally a superuser."

    def add_arguments(self, parser):
        parser.add_argument(
            "--superuser-email",
            type=str,
            help="Email (and username) of the user to make a superuser. Requires --superuser-global-id.",
        )
        parser.add_argument(
            "--superuser-global-id",
            type=str,
            help="Keycloak user ID (global_id) of the user to make a superuser. Requires --superuser-email.",
        )

    def _call(self, *args, **kwargs):
        call_command(*args, stdout=self.stdout, stderr=self.stderr, **kwargs)

    def _seed_courseware(self):
        if Program.objects.filter(readable_id=PROGRAM_ID).exists():
            self.stdout.write(f"Program {PROGRAM_ID} exists, skipping.")
        else:
            self._call(
                "create_courseware",
                "program",
                PROGRAM_ID,
                PROGRAM_TITLE,
                live=True,
                depts=[PROGRAM_DEPARTMENT],
                create_depts=True,
                create_page=True,
            )
            self._call("create_finaid_form", PROGRAM_ID, live=True)

        self._call("configure_tiers", program=PROGRAM_ID)

        for readable_id, title, run_tag, department, required in COURSES:
            if Course.objects.filter(readable_id=readable_id).exists():
                self.stdout.write(f"Course {readable_id} exists, skipping.")
                continue

            self._call(
                "create_courseware",
                "course",
                readable_id,
                title,
                live=True,
                create_run=run_tag,
                program=PROGRAM_ID if required else None,
                required=required,
                depts=[department],
                create_depts=True,
                create_page=True,
                set_courserun_dates_automatically=True,
                price=COURSE_PRICE,
            )

    def _seed_superuser(self, email, global_id):
        User = get_user_model()

        if not User.objects.filter(global_id=global_id).exists():
            stale = User.objects.filter(
                Q(email__iexact=email) | Q(username=email)
            ).first()

            if stale is not None:
                msg = (
                    f"User {stale.id} ({email}) has global_id {stale.global_id}, "
                    f"not {global_id}. This usually means the Keycloak realm was "
                    "recreated after the user was made. Set the user's global_id "
                    f"to {global_id}, or delete the user, and run this command "
                    "again. The courseware is already seeded."
                )
                raise CommandError(msg)

            User.objects.create(global_id=global_id, username=email, email=email)
            self.stdout.write(f"Created user {email} with global_id {global_id}.")

        self._call("promote_user", "promote", "--superuser", "--email", email)

    def handle(self, *args, **kwargs):  # noqa: ARG002
        email = kwargs["superuser_email"]
        global_id = kwargs["superuser_global_id"]

        if bool(email) != bool(global_id):
            msg = "--superuser-email and --superuser-global-id must be given together."
            raise CommandError(msg)

        self.stdout.write(self.style.SUCCESS("Seeding courseware..."))
        with transaction.atomic():
            self._seed_courseware()

        if email:
            self.stdout.write(self.style.SUCCESS(f"Seeding superuser {email}..."))
            with transaction.atomic():
                self._seed_superuser(email, global_id)

        self.stdout.write(self.style.SUCCESS("Done!"))
