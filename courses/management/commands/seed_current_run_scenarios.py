"""
Seeds the courseware and learner needed to exercise MIT Learn's dashboard
"current run" selection (mitodl/hq#12904).

A dashboard course card shows one run out of however many the learner is
enrolled in, with the rest folded into the "Course runs (N)" accordion. The bug
is that the run was chosen by certificate-then-grade, so an ended run could
outrank the run the learner is actually sitting in — and the chosen run was
labelled "In Progress" regardless of its dates. The fix makes the choice purely
date-driven and sources the certificate link from the whole group instead.

Each scenario below is a separate course, so one learner's dashboard shows all
of them at once, and every one is wrong in a visibly different way before the
fix:

    multi-run-grades      3 runs, no certificates, graded
                          -> ended run with the best grade used to win
    multi-run-certificate cert on an ended run, re-enrolled in a live one
                          -> cert run used to win; check the cert link survives
    multi-run-ended       every run is over
                          -> newest ended run, and it must not say "In Progress"
    multi-run-upcoming    every run is still to come
                          -> soonest run, and it must not say "In Progress"

The learner is provisioned in **Keycloak** as well as Django, and the Django row
is stamped with the Keycloak ID. That link is not optional: login matches on
`global_id`, so a Django user without one is never matched — signing in tries to
create a second row, collides on the unique email, and the failure is swallowed,
which shows up as an endless redirect loop at the login screen.

No products or CMS pages are created. Nothing here touches checkout or the
`/courses/<id>` product routes; the cards under test are rendered from the
enrollments API alone.

Usage (local dev runs on the ol-infrastructure Tilt/k3d stack, not compose):
    kubectl exec -it -n mitxonline deploy/mitxonline-webapp -c app -- \\
        python manage.py seed_current_run_scenarios

Re-running is safe: everything is keyed on Keycloak ID, email or readable ID and
updated in place. Run dates are stored relative to "now" at seed time, so re-run
it if the data has aged enough for the live runs to have ended.
"""

import os

import requests
from django.core.management import BaseCommand
from django.db import transaction
from django.utils import timezone

from courses.models import (
    Course,
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
    Department,
    EnrollmentMode,
    Program,
    ProgramEnrollment,
    ProgramRequirement,
)
from openedx.constants import (
    EDX_DEFAULT_ENROLLMENT_MODE,
    EDX_ENROLLMENT_VERIFIED_MODE,
)
from users.models import User

DEPARTMENT_NAME = "Run Selection QA"
KC_TIMEOUT = 15

# Day offsets from seed time. `current` marks the run the dashboard is supposed
# to display, which is what the printout at the end asserts against by eye.
#
# The grades scenario mirrors the enrollments from the original report
# (14.310x): the highest grade sits on the run that ended more than two months
# ago, while the run actually underway is graded lowest.
SCENARIOS = (
    {
        "slug": "GRADES",
        "title": "Graded Runs",
        "expectation": (
            "in-progress run is current, even though an ended run has a higher grade"
        ),
        "runs": (
            {"tag": "R1", "start": -570, "end": -70, "grade": 0.40},
            {"tag": "R2", "start": -210, "end": -80, "grade": 0.12},
            {"tag": "R3", "start": -98, "end": 1, "grade": 0.18, "current": True},
        ),
    },
    {
        "slug": "CERTIFICATE",
        "title": "Certificate Then Re-enrolled",
        "expectation": (
            'in-progress run is current AND "View Certificate" is still shown, '
            "from the ended run that earned it"
        ),
        "runs": (
            {
                "tag": "R1",
                "start": -400,
                "end": -300,
                "grade": 0.92,
                "passed": True,
                "certificate": True,
                "verified": True,
            },
            {"tag": "R2", "start": -30, "end": 30, "current": True},
        ),
    },
    {
        "slug": "ENDED",
        "title": "All Runs Ended",
        "expectation": 'most recent run is current and is NOT labelled "In Progress"',
        "runs": (
            {"tag": "R1", "start": -800, "end": -700},
            {"tag": "R2", "start": -400, "end": -300, "current": True},
        ),
    },
    {
        "slug": "UPCOMING",
        "title": "All Runs Upcoming",
        "expectation": 'soonest run is current and is NOT labelled "In Progress"',
        "runs": (
            {"tag": "R1", "start": 30, "end": 120, "current": True},
            {"tag": "R2", "start": 90, "end": 180},
        ),
    },
)


class Command(BaseCommand):
    """Seed multi-run courses and a learner enrolled in every run."""

    help = __doc__

    def add_arguments(self, parser):
        """Parse arguments."""
        parser.add_argument(
            "--email",
            default="current-run@odl.local",
            help="Learner enrolled in every run of every scenario.",
        )
        parser.add_argument(
            "--password",
            default="localdev123",  # pragma: allowlist secret
            help="Keycloak password to set for the seeded user.",
        )
        parser.add_argument(
            "--keycloak-url",
            # KEYCLOAK_BASE_URL is what the app itself authenticates against, so
            # it is already correct for whichever stack this runs on. The
            # KC_URL/LOCAL_DEV_ROOT_DOMAIN fallback only matters where it is
            # unset.
            default=os.environ.get(
                "KEYCLOAK_BASE_URL",
                os.environ.get(
                    "KC_URL",
                    f"https://sso.ol.{os.environ.get('LOCAL_DEV_ROOT_DOMAIN', 'mit.dev')}",
                ),
            ),
            help="Keycloak base URL. (Default $KEYCLOAK_BASE_URL)",
        )
        parser.add_argument(
            "--keycloak-realm",
            default=os.environ.get("KEYCLOAK_REALM_NAME", "olapps"),
            help="Keycloak realm holding the local-dev users. (Default $KEYCLOAK_REALM_NAME, else olapps)",
        )
        parser.add_argument(
            "--keycloak-admin",
            default="admin",
            help="Keycloak master-realm admin username. (Default admin)",
        )
        parser.add_argument(
            "--keycloak-admin-password",
            default="admin",  # pragma: allowlist secret
            help="Keycloak master-realm admin password. (Default admin)",
        )
        parser.add_argument(
            "--skip-keycloak",
            action="store_true",
            help=(
                "Do not touch Keycloak. The Django user is still seeded, but "
                "without a Keycloak ID it cannot log in — see the warning this "
                "command prints."
            ),
        )
        parser.add_argument(
            "--prefix",
            default="RUNSEL",
            help="Slug fragment used in the generated readable IDs. (Default RUNSEL)",
        )

    # --------------------------------------------------------------- keycloak

    def _kc_token(self, opts):
        """Admin access token, or None if Keycloak is unreachable."""
        try:
            response = requests.post(
                f"{opts['keycloak_url']}/realms/master/protocol/openid-connect/token",
                data={
                    "client_id": "admin-cli",
                    "grant_type": "password",
                    "username": opts["keycloak_admin"],
                    "password": opts["keycloak_admin_password"],
                },
                timeout=KC_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()["access_token"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"  Keycloak unreachable at {opts['keycloak_url']}: {exc}"
                )
            )
            return None

    def _kc_ensure_user(self, token, opts, email):
        """
        Create the Keycloak user if absent and set its password.

        Returns the Keycloak ID, which becomes the Django user's global_id.
        """
        base = f"{opts['keycloak_url']}/admin/realms/{opts['keycloak_realm']}"
        headers = {"Authorization": f"Bearer {token}"}

        def find():
            response = requests.get(
                f"{base}/users",
                params={"email": email, "exact": "true"},
                headers=headers,
                timeout=KC_TIMEOUT,
            )
            response.raise_for_status()
            found = response.json()
            return found[0]["id"] if found else None

        try:
            kc_id = find()
            if kc_id is None:
                # 409 means it raced into existence; the re-find below covers it.
                requests.post(
                    f"{base}/users",
                    json={
                        "username": email,
                        "email": email,
                        "enabled": True,
                        # Skips the verification-email step, which would
                        # otherwise block login on a fresh local stack.
                        "emailVerified": True,
                    },
                    headers=headers,
                    timeout=KC_TIMEOUT,
                )
                kc_id = find()
            if kc_id is None:
                return None
            # Set every run, so the password is always what this command reports.
            requests.put(
                f"{base}/users/{kc_id}/reset-password",
                json={
                    "type": "password",
                    "value": opts["password"],
                    "temporary": False,
                },
                headers=headers,
                timeout=KC_TIMEOUT,
            ).raise_for_status()
        except (requests.RequestException, KeyError, ValueError, IndexError) as exc:
            self.stdout.write(
                self.style.WARNING(f"  Keycloak user {email} not provisioned: {exc}")
            )
            return None
        else:
            return kc_id

    # ------------------------------------------------------------------ user

    def _upsert_user(self, email, name, global_id):
        """
        Get or create the Django user, keyed on the Keycloak ID when we have one.

        Matching on global_id first matters: that is what the API gateway looks
        users up by, so a row found only by email but left unlinked is precisely
        the state that breaks login.
        """
        user = None
        if global_id:
            user = User.objects.filter(global_id=global_id).first()
        if user is None:
            user = User.objects.filter(email=email).first()

        if user is not None:
            if global_id and user.global_id != global_id:
                user.global_id = global_id
                user.save(update_fields=["global_id"])
            return user, False

        # Deliberately create_user() rather than get_or_create(): the related
        # LegalAddress, UserProfile and OpenEdxUser records are built by
        # _post_create_user, which only the manager method runs.
        user = User.objects.create_user(
            username=email,
            email=email,
            password=None,
            name=name,
            is_active=True,
            global_id=global_id or None,
        )
        return user, True

    # ---------------------------------------------------- courseware records

    def _enrollment_modes(self):
        """The audit and verified modes a run offers."""
        audit, _ = EnrollmentMode.objects.get_or_create(
            mode_slug=EDX_DEFAULT_ENROLLMENT_MODE,
            defaults={"requires_payment": False},
        )
        verified, _ = EnrollmentMode.objects.get_or_create(
            mode_slug=EDX_ENROLLMENT_VERIFIED_MODE,
            defaults={"requires_payment": True},
        )
        return audit, verified

    def _upsert_course(self, readable_id, title, department):
        course, _ = Course.objects.update_or_create(
            readable_id=readable_id,
            defaults={"title": title, "live": True},
        )
        course.departments.add(department)
        return course

    def _upsert_run(self, course, readable_id, title, spec, modes):
        """
        One run of a scenario course, dated by `spec`'s day offsets.

        The dates are the entire point of these fixtures — `start_date` and
        `end_date` are what the selection policy reads, and the accordion reads
        them again to decide whether the run may be called "In Progress".
        """
        now = timezone.now()
        start = now + timezone.timedelta(days=spec["start"])
        end = now + timezone.timedelta(days=spec["end"])
        run, _ = CourseRun.objects.update_or_create(
            courseware_id=readable_id,
            defaults={
                "course": course,
                "title": f"{title} ({spec['tag']})",
                "run_tag": spec["tag"],
                "has_courseware_url": True,
                "live": True,
                "is_self_paced": True,
                "start_date": start,
                "end_date": end,
                "enrollment_start": start - timezone.timedelta(days=14),
                "enrollment_end": end,
                # No product is created for these runs, so there is nothing to
                # upgrade to; leaving this null keeps the upgrade banner out of
                # the way of the certificate link being tested.
                "upgrade_deadline": None,
                "b2b_contract": None,
            },
        )
        run.enrollment_modes.set(modes)
        return run

    def _upsert_enrollment(self, user, run, spec):
        enrollment, _ = CourseRunEnrollment.objects.update_or_create(
            user=user,
            run=run,
            defaults={
                "active": True,
                "change_status": None,
                "enrollment_mode": (
                    EDX_ENROLLMENT_VERIFIED_MODE
                    if spec.get("verified")
                    else EDX_DEFAULT_ENROLLMENT_MODE
                ),
                "edx_enrolled": False,
            },
        )
        return enrollment

    def _upsert_grade(self, user, run, spec):
        """A final grade, which is what the old policy ranked runs by."""
        if "grade" not in spec:
            return None
        grade, _ = CourseRunGrade.objects.update_or_create(
            user=user,
            course_run=run,
            defaults={
                "grade": spec["grade"],
                "passed": spec.get("passed", False),
                "set_by_admin": True,
            },
        )
        return grade

    def _upsert_certificate(self, user, run, spec):
        """
        A course-run certificate on an ended run.

        Looked up through `all_objects`: the default manager hides revoked
        certificates, so a revoked row would be invisible to update_or_create
        and the unique (user, course_run) insert behind it would fail.
        """
        if not spec.get("certificate"):
            return None
        certificate, _ = CourseRunCertificate.all_objects.update_or_create(
            user=user,
            course_run=run,
            defaults={"is_revoked": False},
        )
        return certificate

    def _upsert_program(self, readable_id, title, courses, modes):
        """
        A program requiring every scenario course.

        The original report came from a program dashboard's requirement
        section, which renders the cards through a different path than the home
        dashboard, so both need to be reachable from the seeded data.
        """
        now = timezone.now()
        program, _ = Program.objects.update_or_create(
            readable_id=readable_id,
            defaults={
                "title": title,
                "live": True,
                "enrollment_start": now - timezone.timedelta(days=14),
                "enrollment_end": now + timezone.timedelta(days=90),
            },
        )
        program.enrollment_modes.set(modes)

        # Clear this program's course nodes before re-adding: add_requirement
        # only dedups against the requirements root's direct children, while the
        # nodes it creates live a level deeper, so every re-run would otherwise
        # append another copy of each course.
        for node in ProgramRequirement.objects.filter(
            program=program, course__in=courses
        ):
            node.delete()

        for course in courses:
            program.add_requirement(course)
        return program

    # ----------------------------------------------------------------- handle

    @transaction.atomic
    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Seed the courseware and learner, then print what to check."""
        prefix = kwargs["prefix"]
        department, _ = Department.objects.get_or_create(name=DEPARTMENT_NAME)
        modes = list(self._enrollment_modes())

        self.stdout.write(self.style.MIGRATE_HEADING("User"))
        token = None if kwargs["skip_keycloak"] else self._kc_token(kwargs)
        kc_id = self._kc_ensure_user(token, kwargs, kwargs["email"]) if token else None
        user, created = self._upsert_user(kwargs["email"], "Current Run QA", kc_id)
        self.stdout.write(
            f"  {user.email} ({'created' if created else 'reused'})"
            + (f"\n      keycloak: {user.global_id}" if user.global_id else "")
        )

        self.stdout.write(self.style.MIGRATE_HEADING("Courseware"))
        courses = []
        expectations = []
        for scenario in SCENARIOS:
            readable_id = f"course-v1:MITxT+{prefix}-{scenario['slug']}"
            title = f"[{prefix}] {scenario['title']}"
            course = self._upsert_course(readable_id, title, department)
            courses.append(course)

            current_run = None
            for spec in scenario["runs"]:
                run = self._upsert_run(
                    course, f"{readable_id}+{spec['tag']}", title, spec, modes
                )
                self._upsert_enrollment(user, run, spec)
                self._upsert_grade(user, run, spec)
                self._upsert_certificate(user, run, spec)
                if spec.get("current"):
                    current_run = run

            self.stdout.write(
                f"  course  {readable_id} ({len(scenario['runs'])} runs, enrolled)"
            )
            for spec in scenario["runs"]:
                marks = [
                    f"grade {spec['grade']}" if "grade" in spec else None,
                    "certificate" if spec.get("certificate") else None,
                    "<- expected current run" if spec.get("current") else None,
                ]
                detail = ", ".join(mark for mark in marks if mark)
                self.stdout.write(
                    f"      {spec['tag']}: day {spec['start']:+d} to {spec['end']:+d}"
                    + (f"  ({detail})" if detail else "")
                )
            expectations.append((title, current_run, scenario["expectation"]))

        program_id = f"program-v1:MITxT+{prefix}-PROGRAM"
        program = self._upsert_program(
            program_id, f"[{prefix}] Current Run Program", courses, modes
        )
        ProgramEnrollment.objects.update_or_create(
            user=user,
            program=program,
            defaults={
                "active": True,
                "change_status": None,
                "enrollment_mode": EDX_DEFAULT_ENROLLMENT_MODE,
            },
        )
        self.stdout.write(
            f"  program {program_id} ({len(courses)} required courses, enrolled)"
        )

        self.stdout.write(self.style.MIGRATE_HEADING("What to check"))
        self.stdout.write(
            f"  Sign in as {kwargs['email']}, then open /dashboard and "
            f"/dashboard/program/{program.id} — the cards render through "
            "different code paths on each."
        )
        self.stdout.write(
            "  Expand each card's 'Course runs (N)' accordion and compare the "
            "'Current run:' row against:"
        )
        for title, current_run, expectation in expectations:
            self.stdout.write(f"    {title}")
            self.stdout.write(f"      {expectation}")
            if current_run:
                self.stdout.write(f"      expected run: {current_run.courseware_id}")

        if not user.global_id:
            # Left unlinked, this row actively breaks login: the gateway looks
            # users up by global_id, fails to match, tries to create a second
            # row and collides on the unique email. The exception is swallowed,
            # so the symptom is an endless redirect loop rather than an error.
            self.stdout.write(
                self.style.ERROR(
                    f"\nNo Keycloak ID for {user.email}. This user cannot log in, "
                    "and will loop at the login screen if you try. Re-run without "
                    "--skip-keycloak, or with --keycloak-url pointing at a "
                    "reachable Keycloak."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n{user.email} is provisioned in Keycloak "
                    f"(realm {kwargs['keycloak_realm']}) and linked. "
                    f"Password: {kwargs['password']}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS("Done. Re-run any time to re-date every run.")
        )
