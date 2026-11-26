import json
import ssl
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

import pymysql
import trino.dbapi
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from mitol.common.utils.datetime import now_in_utc
from reversion.models import Version
from trino.auth import BasicAuthentication

from cms.api import create_default_courseware_page
from cms.models import CertificatePage, SignatoryPage
from courses.models import (
    Course,
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
    CourseRunGradeAudit,
    Department,
    Program,
    ProgramCertificate,
    ProgramEnrollment,
)
from ecommerce.api import fulfill_completed_order
from ecommerce.constants import ZERO_PAYMENT_DATA
from ecommerce.models import Discount, Order, OrderStatus, PendingOrder, Product
from openedx.api import repair_faulty_edx_user
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
from users.models import GENDER_CHOICES, LegalAddress, User, UserProfile

# StarRocks fails a query whose result is still being read query_timeout seconds
# after it started (default 300), and the results below are streamed while each
# batch is written to the database, so a large type would outlive the default.
STARROCKS_QUERY_TIMEOUT_SECONDS = 24 * 60 * 60
WAREHOUSE_TRINO = "trino"
WAREHOUSE_STARROCKS = "starrocks"
WAREHOUSE_REQUIRED_SETTINGS = {
    WAREHOUSE_TRINO: ("TRINO_HOST", "TRINO_USER", "TRINO_CATALOG"),
    WAREHOUSE_STARROCKS: ("STARROCKS_HOST", "STARROCKS_USER"),
}

MIGRATION_SCHEMA = "ol_warehouse_production_migration"
# The data platform builds these tables in the production lake only. StarRocks
# exposes it under this catalog; Trino's catalog name comes from TRINO_CATALOG.
STARROCKS_CATALOG = "ol_data_lake_production"

PLATFORM_EDXORG = "edxorg"
# The mitxonline_migration_* tables hold every other platform, one per value of
# their source column. Add a platform here when the data platform adds its source.
MIGRATION_TABLE_PLATFORMS = ("xpro",)
PLATFORMS = (PLATFORM_EDXORG, *MIGRATION_TABLE_PLATFORMS)


def _uses_trino():
    return settings.EDX_MIGRATION_WAREHOUSE == WAREHOUSE_TRINO


def _warehouse_table(table_name):
    catalog = settings.TRINO_CATALOG if _uses_trino() else STARROCKS_CATALOG
    return f"{catalog}.{MIGRATION_SCHEMA}.{table_name}"


def _warehouse_placeholders(count):
    """Query placeholders in the warehouse driver's paramstyle"""
    placeholder = "?" if _uses_trino() else "%s"
    return ", ".join([placeholder] * count)


def _warehouse_list(value):
    """Read an array column. Trino sends a list, StarRocks sends JSON text."""
    if value is None:
        return []
    if isinstance(value, str | bytes):
        return json.loads(value)
    return list(value)


def _platform_table(name, platform):
    """The table and the WHERE conditions that select one platform's rows"""
    if platform == PLATFORM_EDXORG:
        return _warehouse_table(f"edxorg_to_mitxonline_{name}"), []
    # platform is one of MIGRATION_TABLE_PLATFORMS, so it is safe to inline
    return _warehouse_table(f"mitxonline_migration_{name}"), [f"source = '{platform}'"]


def _select_query(table, conditions, limit=None):
    query = f"SELECT * FROM {table}"  # noqa: S608
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    return query


def _warehouse_datetime(value):
    """Read a timestamp column. StarRocks sends it naive, in the session's time zone,
    which _connect_to_starrocks sets to UTC. The mitxonline_migration_* tables send
    ISO 8601 text.
    """
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _connect_to_trino():
    return trino.dbapi.connect(
        host=settings.TRINO_HOST,
        port=settings.TRINO_PORT,
        user=settings.TRINO_USER,
        auth=BasicAuthentication(settings.TRINO_USER, settings.TRINO_PASSWORD),
        catalog=settings.TRINO_CATALOG,
        schema=MIGRATION_SCHEMA,
    )


def _connect_to_starrocks():
    return pymysql.connect(
        host=settings.STARROCKS_HOST,
        port=settings.STARROCKS_PORT,
        user=settings.STARROCKS_USER,
        password=settings.STARROCKS_PASSWORD,
        # Verifies the chain against the system CAs and the hostname.
        # pymysql skips the hostname check when ssl_ca is unset, even
        # with ssl_verify_identity=True, so a context is passed instead.
        ssl=ssl.create_default_context(),
        # Stream rows as fetchmany asks for them, as the Trino client does;
        # the default cursor reads the whole result into memory at execute.
        cursorclass=pymysql.cursors.SSCursor,
        # StarRocks renders a timestamp with time zone in the session's
        # time zone, and sends it without one.
        init_command=(
            "SET time_zone = '+00:00', "
            f"query_timeout = {STARROCKS_QUERY_TIMEOUT_SECONDS}"
        ),
    )


@dataclass(frozen=True)
class _CertificateColumns:
    model: type
    object_field: str
    object_column: str
    uuid_column: str
    revoked_column: str
    issued_column: str


COURSE_RUN_CERTIFICATE_COLUMNS = _CertificateColumns(
    model=CourseRunCertificate,
    object_field="course_run_id",
    object_column="courserun_id",
    uuid_column="courseruncertificate_uuid",
    revoked_column="courseruncertificate_is_revoked",
    issued_column="courseruncertificate_created_on",
)
PROGRAM_CERTIFICATE_COLUMNS = _CertificateColumns(
    model=ProgramCertificate,
    object_field="program_id",
    object_column="program_id",
    uuid_column="programcertificate_uuid",
    revoked_column="programcertificate_is_revoked",
    issued_column="program_certificate_issued_on",
)


class Command(BaseCommand):
    help = (
        "Migrate edX.org, xPRO or other platform data via the data platform's warehouse "
        "(Trino or StarRocks, per EDX_MIGRATION_WAREHOUSE) to the corresponding models "
        "in MITx Online e.g Course, CourseRun, CoursePage CertificatePage, etc."
    )

    def _connect_to_warehouse(self):
        warehouse = settings.EDX_MIGRATION_WAREHOUSE
        if warehouse not in WAREHOUSE_REQUIRED_SETTINGS:
            msg = (
                f"EDX_MIGRATION_WAREHOUSE must be one of "
                f"{', '.join(WAREHOUSE_REQUIRED_SETTINGS)}, not {warehouse!r}"
            )
            raise CommandError(msg)
        missing = [
            name
            for name in WAREHOUSE_REQUIRED_SETTINGS[warehouse]
            if not getattr(settings, name)
        ]
        if missing:
            msg = f"{', '.join(missing)} must be set to read the edX migration tables from {warehouse}"
            raise CommandError(msg)
        try:
            conn = (
                _connect_to_trino()
                if warehouse == WAREHOUSE_TRINO
                else _connect_to_starrocks()
            )
            self.stdout.write(
                self.style.SUCCESS(f"Successfully connected to {warehouse}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to connect to {warehouse}: {e}")
            )
            raise
        else:
            return conn

    def _create_course(self, row):
        """
        Create a new Course instance or get an existing one using data from the row.

        Args:
            row (dict): Dictionary containing course data from the warehouse

        Returns:
            tuple: Tuple containing (Course instance, boolean indicating if created)
            - Course instance: The created or retrieved Course model instance
            - boolean: True if a new course was created, False if existing was retrieved
        """
        course, created = Course.objects.get_or_create(
            readable_id=row.get("course_readable_id"),
            defaults={
                "title": row.get("course_title"),
                "readable_id": row.get("course_readable_id"),
                "live": False,
            },
        )
        # Only the edX.org table has departments
        if row.get("department_name"):
            department, _ = Department.objects.get_or_create(
                name=row["department_name"]
            )
            course.departments.add(department)
        course.save()

        return course, created

    def _create_course_certificate_page(self, course_page, course_title, signatories):
        """
        Create a certificate page for a course and associate it with a signatory.

        Args:
            course_page: The course page to create the certificate page under
            course_title: Title of the course to use in certificate
            signatories: The SignatoryPage instances to associate with the certificate

        Returns:
            The created CertificatePage instance

        """
        certificate_page = course_page.add_child(
            instance=CertificatePage(
                product_name=course_title,
                title=f"Certificate For {course_title}",
                live=True,
            )
        )

        if signatories:
            # Create the signatory block with only required fields
            signatory_blocks = [
                {"type": "signatory", "value": signatory.id}
                for signatory in signatories
            ]
            certificate_page.signatories = signatory_blocks

        # Save the page first to create the initial content
        certificate_page.save()

        # Create a new revision
        revision = certificate_page.save_revision()
        revision.publish()

        return certificate_page

    def _create_course_run(self, course, row, *, live=True):
        """
        Create a new CourseRun instance for the given course using data from row.

        Args:
            course (Course): Course model instance to create the run for
            row (dict): Dictionary containing course run data from the warehouse
            live (bool): Whether the new course run is live

        Returns:
            tuple: Tuple containing (CourseRun instance, boolean indicating if created)
        """
        course_run, created_run = CourseRun.objects.get_or_create(
            courseware_id=row.get("courseware_id"),
            defaults={
                "course": course,
                "run_tag": row.get("run_tag"),
                "start_date": _warehouse_datetime(row.get("start_date")),
                "end_date": _warehouse_datetime(row.get("end_date")),
                "enrollment_start": _warehouse_datetime(row.get("enrollment_start")),
                "enrollment_end": _warehouse_datetime(row.get("enrollment_end")),
                "title": row.get("courserun_title"),
                "live": live,
                "is_self_paced": row.get("is_self_paced"),
            },
        )
        return course_run, created_run

    def _get_signatories(self, signatory_list, use_default_signatory):
        """
        Get SignatoryPage based on the provided list of names or use the default signatory.

        Args:
            signatory_list (str | None): The signatory_names array column, as StarRocks sends it
            use_default_signatory: Boolean indicating whether to use the default signatory

        Returns:
            list: List of SignatoryPage
        """
        if use_default_signatory:
            signatory_obj = SignatoryPage.objects.first()
            if not signatory_obj:
                self.stdout.write(
                    self.style.ERROR(
                        "No signatory found in the system. Please create at least one SignatoryPage instance."
                    )
                )
                exit(-1)  # noqa: PLR1722
            return [signatory_obj]

        signatory_names = [
            name.strip()
            for name in _warehouse_list(signatory_list)
            if isinstance(name, str) and name.strip()
        ]
        return list(SignatoryPage.objects.filter(name__in=signatory_names))

    def _migrate_course_runs(self, conn, options):
        """
        Migrate course runs,their associated courses, course pages, and course certificate pages
        """
        use_default_signatory = options["use_default_signatory"]
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)
        platform = options.get("platform", PLATFORM_EDXORG)
        is_edxorg = platform == PLATFORM_EDXORG

        cur = conn.cursor()

        cur.execute(_select_query(*_platform_table("course_runs", platform), limit))
        columns = [desc[0] for desc in cur.description]

        course_success_count = 0
        run_success_count = 0

        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            for result in results:
                row = dict(zip(columns, result))
                # Skip rows with no department courses or any course with no
                # certificates. The other tables hold only the runs to create.
                if is_edxorg and (
                    (
                        not row.get("department_name")
                        and row.get("mitxonline_course_id") is None
                    )
                    or (
                        row.get("certificate_count") is None
                        or int(row.get("certificate_count", 0)) < 1
                    )
                ):
                    continue

                signatories = self._get_signatories(
                    row.get("signatory_names"), use_default_signatory
                )

                # Only the edX.org table has signatory names
                if (
                    is_edxorg
                    and not signatories
                    and row.get("mitxonline_course_id") is None
                ):
                    self.stdout.write(
                        self.style.ERROR(
                            f"No valid signatories found with names {row.get('signatory_names')} for course "
                            f"{row.get('course_readable_id')}, skipping it."
                        )
                    )
                    continue

                (course, course_created) = self._create_course(row)

                if course_created:
                    try:
                        course_page = create_default_courseware_page(course, live=False)
                        self._create_course_certificate_page(
                            course_page, row.get("course_title"), signatories
                        )
                        course_success_count += 1

                    except Exception as e:  # noqa: BLE001
                        self.stdout.write(
                            self.style.ERROR(
                                f"Could not create CMS page {course.readable_id}, skipping it: {e}"
                            )
                        )

                # edX.org runs are always live; the other platforms send their own status
                _, run_created = self._create_course_run(
                    course, row, live=is_edxorg or bool(row.get("is_published"))
                )
                if run_created:
                    run_success_count += 1

        self.stdout.write(self.style.SUCCESS(f"{course_success_count} courses created"))
        self.stdout.write(
            self.style.SUCCESS(f"{run_success_count} course runs created")
        )

    @staticmethod
    def _bulk_create_users(rows, existing_emails, batch_size):
        """
        Create users in bulk, skipping those with existing emails.
        """
        new_users = []
        new_emails = []
        for row in rows:
            email = row.get("user_email")
            if not email or email in existing_emails:
                continue
            user = User(
                username=email,
                email=email,
                name=row.get("user_full_name"),
                is_staff=False,
                is_active=True,
                is_superuser=False,
            )
            user.set_unusable_password()
            new_users.append(user)
            new_emails.append(email)

        User.objects.bulk_create(
            new_users, batch_size=batch_size, ignore_conflicts=True
        )

        if not new_emails:
            return []

        # bulk_create never populates .pk on the returned objects when
        # ignore_conflicts=True is used - on any database backend, per
        # Django's own documented behavior, since it can't reliably map a
        # generated id back to a specific input object once some rows may
        # have been silently skipped on conflict. Re-fetch by email (unique
        # per users_user_email_unique) to get real ids for
        # _bulk_create_legal_addresses/_bulk_create_user_profiles to key off
        # of - without this, those two methods filter on ids that are all
        # None, match zero rows, and silently never create anything.
        return list(User.objects.filter(email__in=new_emails))

    @staticmethod
    def _bulk_create_legal_addresses(created_users, row_lookup_by_id, batch_size):
        """
        Create legal addresses in bulk for the given users.

        Only creates records for users that do not already have a LegalAddress.
        Uses a blank country when none is provided in the row data.
        """
        legal_addresses = []
        user_ids = [user.id for user in created_users]
        saved_users = User.objects.filter(id__in=user_ids)

        existing_user_ids = set(
            LegalAddress.objects.filter(user_id__in=user_ids).values_list(
                "user_id", flat=True
            )
        )

        for user in saved_users:
            if user.id in existing_user_ids:
                continue
            user_data = row_lookup_by_id.get(user.id)
            if not user_data:
                continue
            country = user_data.get("user_address_country") or ""
            legal_addresses.append(
                LegalAddress(
                    user=user,
                    country=country,
                    state=user_data.get("user_address_state") or None,
                    postal_code=user_data.get("user_address_postal_code") or "",
                    street_address_1=user_data.get("user_address_street_1") or "",
                    street_address_2=user_data.get("user_address_street_2") or "",
                    city=user_data.get("user_address_city") or "",
                )
            )
        if legal_addresses:
            LegalAddress.objects.bulk_create(
                legal_addresses, batch_size=batch_size, ignore_conflicts=True
            )

    @staticmethod
    def _bulk_create_user_profiles(
        created_users, row_lookup_by_id, batch_size, gender_map
    ):
        """
        Create user profiles in bulk for the given users.

        Only creates records for users that do not already have a UserProfile.
        Uses blank gender and year_of_birth when none is provided in the row data.
        """
        user_profiles = []
        user_ids = [user.id for user in created_users]
        saved_users = User.objects.filter(id__in=user_ids)

        existing_user_ids = set(
            UserProfile.objects.filter(user_id__in=user_ids).values_list(
                "user_id", flat=True
            )
        )

        for user in saved_users:
            if user.id in existing_user_ids:
                continue
            user_data = row_lookup_by_id.get(user.id)
            if not user_data:
                continue
            gender = user_data.get("user_gender")
            birth_year = user_data.get("user_birth_year")
            user_profiles.append(
                UserProfile(
                    user=user, year_of_birth=birth_year, gender=gender_map.get(gender)
                )
            )
        if user_profiles:
            UserProfile.objects.bulk_create(
                user_profiles, batch_size=batch_size, ignore_conflicts=True
            )

    def _migrate_users(self, conn, options):
        """
        Migrate users from edX.org or another platform to MITx Online. Create User, LegalAddress, and UserProfile instances.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)
        dry_run = options.get("dry_run")
        platform = options.get("platform", PLATFORM_EDXORG)

        cur = conn.cursor()

        cur.execute(_select_query(*_platform_table("users", platform), limit))
        columns = [desc[0] for desc in cur.description]

        # e.g. {"Male": "m", "Female": "f"}
        GENDER_MAP = {label: code for code, label in GENDER_CHOICES}

        user_creation_count = 0
        # dry-run only: lowercased emails already counted, across batches
        dry_run_counted = set()
        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            rows = [dict(zip(columns, r)) for r in results]

            row_lookup = {
                row["user_email"]: row for row in rows if row.get("user_email")
            }
            emails = list(row_lookup.keys())

            # usernames too: migrated users get username=email, so an email
            # matching an existing username would conflict on create
            existing_emails = {
                value
                for pair in User.objects.filter(
                    Q(username__in=emails) | Q(email__in=emails)
                ).values_list("username", "email")
                for value in pair
            }

            if dry_run:
                # email uniqueness is case-insensitive (user_email_unique), so
                # count the way a real run's inserts would succeed or conflict
                existing_lower = set(
                    User.objects.annotate(email_lower=Lower("email"))
                    .filter(email_lower__in=[email.lower() for email in emails])
                    .values_list("email_lower", flat=True)
                )
                for email in emails:
                    key = email.lower()
                    if (
                        email not in existing_emails
                        and key not in existing_lower
                        and key not in dry_run_counted
                    ):
                        dry_run_counted.add(key)
                        user_creation_count += 1
                continue

            created_users = self._bulk_create_users(rows, existing_emails, batch_size)
            user_creation_count += len(created_users)

            id_row_lookup = {
                user.id: row_lookup[user.email]
                for user in created_users
                if user.email in row_lookup
            }
            self._bulk_create_legal_addresses(created_users, id_row_lookup, batch_size)
            self._bulk_create_user_profiles(
                created_users, id_row_lookup, batch_size, GENDER_MAP
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would create {user_creation_count} users"
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f"{user_creation_count} users created"))

    def _repair_migrated_user_profiles(self, conn, options):
        """
        Backfill LegalAddress/UserProfile rows for users left without them by
        a historical bug in _bulk_create_users: bulk_create(ignore_conflicts=True)
        never populates .pk on the objects passed into it, so every call here
        used to build id_row_lookup keyed on user.id=None and then filter
        User.objects.filter(id__in=[None, ...]), which always matches zero
        rows - LegalAddress/UserProfile silently never got created for any
        user who went through this command, regardless of the row data
        the warehouse actually had for them.

        This re-scans the same edX table used by _migrate_users, but only
        acts on users already missing one of these rows - real, already-saved
        User objects with real ids, so the existing bulk-create helpers work
        correctly here the same way they already do for the enrollments
        migration's opportunistic repair path.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)
        dry_run = options.get("dry_run")

        affected_users = list(
            User.objects.filter(
                Q(legal_address__isnull=True) | Q(user_profile__isnull=True)
            ).only("id", "email")
        )
        if limit is not None:
            affected_users = affected_users[:limit]
        affected_by_email = {user.email: user for user in affected_users if user.email}

        self.stdout.write(
            f"{len(affected_by_email)} users found missing "
            f"LegalAddress and/or UserProfile"
        )

        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {_warehouse_table('edxorg_to_mitxonline_users')}")  # noqa: S608
        columns = [desc[0] for desc in cur.description]

        # e.g. {"Male": "m", "Female": "f"}
        GENDER_MAP = {label: code for code, label in GENDER_CHOICES}

        repaired_emails = set()
        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            rows = [dict(zip(columns, r)) for r in results]

            matched_users = []
            row_lookup_by_id = {}
            for row in rows:
                email = row.get("user_email")
                user = affected_by_email.get(email)
                if user is None or email in repaired_emails:
                    continue
                matched_users.append(user)
                row_lookup_by_id[user.id] = row
                repaired_emails.add(email)

            if not matched_users:
                continue

            if dry_run:
                continue

            self._bulk_create_legal_addresses(
                matched_users, row_lookup_by_id, batch_size
            )
            self._bulk_create_user_profiles(
                matched_users, row_lookup_by_id, batch_size, GENDER_MAP
            )

        unmatched = len(affected_by_email) - len(repaired_emails)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would repair {len(repaired_emails)} users"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Repaired {len(repaired_emails)} users")
            )
        if unmatched:
            self.stdout.write(
                self.style.WARNING(
                    f"{unmatched} affected users had no matching row in "
                    f"edxorg_to_mitxonline_users - still missing "
                    f"LegalAddress/UserProfile, needs manual review"
                )
            )

    @staticmethod
    def _bulk_create_enrollments(
        rows,
        batch_size,
        edx_enrolled=True,  # noqa: FBT002
    ):
        new_enrollment_objects = [
            CourseRunEnrollment(
                user_id=row["user_mitxonline_id"],
                run_id=row["courserun_id"],
                enrollment_mode=row["courserunenrollment_enrollment_mode"],
                edx_enrolled=edx_enrolled,
                edx_emails_subscription=False,
                active=True,
            )
            for row in rows
        ]
        if not new_enrollment_objects:
            return 0

        CourseRunEnrollment.objects.bulk_create(
            new_enrollment_objects,
            batch_size=batch_size,
            ignore_conflicts=True,
        )
        return len(new_enrollment_objects)

    @staticmethod
    def _bulk_create_grades(rows, batch_size):
        new_grade_objects = [
            CourseRunGrade(
                user_id=row["user_mitxonline_id"],
                course_run_id=row["courserun_id"],
                grade=row["courserungrade_grade"],
                passed=bool(row["courserungrade_is_passing"]),
                letter_grade=row.get("courserungrade_letter_grade"),
            )
            for row in rows
        ]

        if not new_grade_objects:
            return 0

        CourseRunGrade.objects.bulk_create(
            new_grade_objects, batch_size=batch_size, ignore_conflicts=True
        )
        return len(new_grade_objects)

    @staticmethod
    def _bulk_create_certificates(rows, batch_size):
        new_certificate_objects = [
            CourseRunCertificate(
                user_id=row["user_mitxonline_id"],
                course_run_id=row["courserun_id"],
                issue_date=_warehouse_datetime(row["courseruncertificate_created_on"]),
                certificate_page_revision_id=row["certificate_page_revision_id"],
            )
            for row in rows
        ]
        if not new_certificate_objects:
            return 0

        CourseRunCertificate.objects.bulk_create(
            new_certificate_objects, batch_size=batch_size, ignore_conflicts=True
        )
        return len(new_certificate_objects)

    @staticmethod
    def _courserun_filter(options):
        readable_ids = [
            readable_id.strip()
            for readable_id in (options.get("courserun_readable_ids") or "").split(",")
            if readable_id.strip()
        ]
        if not readable_ids:
            return None, []
        placeholders = _warehouse_placeholders(len(readable_ids))
        return f"courserun_readable_id IN ({placeholders})", readable_ids

    def _migrate_course_certificates(self, conn, options):
        """
        Migrate certificates from edX to MITx Online. Create CourseRunEnrollment, CourseRunGrade,
        and CourseRunCertificate instances.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)
        dry_run = options.get("dry_run")
        cur = conn.cursor()

        query = (
            f"SELECT * FROM {_warehouse_table('edxorg_to_mitxonline_enrollments')} "  # noqa: S608
            "WHERE user_mitxonline_id IS NOT NULL AND courserun_id IS NOT NULL "
            "AND courseruncertificate_created_on IS NOT NULL"
        )
        courserun_filter, params = self._courserun_filter(options)
        if courserun_filter:
            query += f" AND {courserun_filter}"

        if limit is not None:
            query += f" LIMIT {int(limit)}"

        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]

        total_enrollments = 0
        total_grades = 0
        total_certificates = 0
        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            rows = [dict(zip(columns, r)) for r in results]

            if dry_run:
                count = len(rows)
                total_enrollments += count
                total_grades += count
                total_certificates += count

                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY RUN] Would create "
                        f"{total_enrollments} enrollments, "
                        f"{total_grades} grades, "
                        f"{total_certificates} certificates"
                    )
                )
            else:
                # Bulk create enrollments, grades, and certificates
                total_enrollments += self._bulk_create_enrollments(rows, batch_size)
                total_grades += self._bulk_create_grades(rows, batch_size)
                total_certificates += self._bulk_create_certificates(rows, batch_size)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"{total_enrollments} enrollments created, "
                        f"{total_grades} grades created, "
                        f"{total_certificates} certificates created"
                    )
                )

    @staticmethod
    def _update_letter_grades(rows, *, dry_run):
        """
        Set letter_grade on the CourseRunGrade rows that match the given rows. Grades
        that already have a letter grade are not changed.

        Returns:
            int: The number of grades updated, or that would be updated on a dry run
        """
        letter_by_key = {
            (row["user_mitxonline_id"], row["courserun_id"]): row[
                "courserungrade_letter_grade"
            ]
            for row in rows
            if row["courserungrade_letter_grade"]
        }
        if not letter_by_key:
            return 0

        user_ids = {user_id for user_id, _ in letter_by_key}
        run_ids = {run_id for _, run_id in letter_by_key}
        with transaction.atomic():
            candidates = (
                CourseRunGrade.objects.select_for_update()
                .filter(user_id__in=user_ids, course_run_id__in=run_ids)
                .filter(Q(letter_grade__isnull=True) | Q(letter_grade=""))
            )
            grades = [
                grade
                for grade in candidates
                if (grade.user_id, grade.course_run_id) in letter_by_key
            ]
            if dry_run or not grades:
                return len(grades)

            # bulk_update skips save_and_log, so the audit rows are written here
            now = now_in_utc()
            audits = []
            for grade in grades:
                data_before = grade.to_dict()
                grade.letter_grade = letter_by_key[(grade.user_id, grade.course_run_id)]
                grade.updated_on = now
                audits.append(
                    CourseRunGradeAudit(
                        course_run_grade=grade,
                        acting_user=None,
                        call_stack="migrate_edx_data --type letter_grades",
                        data_before=data_before,
                        data_after=grade.to_dict(),
                    )
                )
            CourseRunGrade.objects.bulk_update(grades, ["letter_grade", "updated_on"])
            CourseRunGradeAudit.objects.bulk_create(audits)
        return len(grades)

    def _backfill_letter_grades(self, conn, options):
        """
        Backfill letter grades from edX.org for CourseRunGrade rows that have none,
        such as the grades that the course_certificates migration created.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)
        dry_run = options.get("dry_run")
        cur = conn.cursor()

        query = (
            "SELECT user_mitxonline_id, courserun_id, courserungrade_letter_grade "  # noqa: S608
            f"FROM {_warehouse_table('edxorg_to_mitxonline_letter_grades')}"
        )
        courserun_filter, params = self._courserun_filter(options)
        if courserun_filter:
            query += f" WHERE {courserun_filter}"

        if limit is not None:
            query += f" LIMIT {int(limit)}"

        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]

        total_rows = 0
        total_updated = 0
        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            rows = [dict(zip(columns, r)) for r in results]
            total_rows += len(rows)
            total_updated += self._update_letter_grades(rows, dry_run=dry_run)

        prefix = "[DRY RUN] Would update" if dry_run else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix} {total_updated} letter grades "
                f"from {total_rows} edX.org letter grade rows"
            )
        )

    @staticmethod
    def _bulk_create_program_enrollments(rows, batch_size):
        user_ids = {row["user_mitxonline_id"] for row in rows}
        program_ids = {row["program_id"] for row in rows}
        existing = set(
            ProgramEnrollment.all_objects.filter(
                user_id__in=user_ids,
                program_id__in=program_ids,
            ).values_list("user_id", "program_id")
        )
        new_enrollment_objects = [
            ProgramEnrollment(
                user_id=row["user_mitxonline_id"],
                program_id=row["program_id"],
                enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
            )
            for row in rows
            if (row["user_mitxonline_id"], row["program_id"]) not in existing
        ]
        if not new_enrollment_objects:
            return 0

        ProgramEnrollment.all_objects.bulk_create(
            new_enrollment_objects,
            batch_size=batch_size,
            ignore_conflicts=True,
        )
        return len(new_enrollment_objects)

    @staticmethod
    def _bulk_create_program_certificates(rows, batch_size):
        user_ids = {row["user_mitxonline_id"] for row in rows}
        program_ids = {row["program_id"] for row in rows}
        existing = set(
            ProgramCertificate.all_objects.filter(
                user_id__in=user_ids,
                program_id__in=program_ids,
            ).values_list("user_id", "program_id")
        )
        new_certificate_objects = [
            ProgramCertificate(
                user_id=row["user_mitxonline_id"],
                program_id=row["program_id"],
                issue_date=_warehouse_datetime(row["program_certificate_issued_on"]),
                certificate_page_revision_id=row["certificate_page_revision_id"],
            )
            for row in rows
            if (row["user_mitxonline_id"], row["program_id"]) not in existing
        ]
        if not new_certificate_objects:
            return 0

        ProgramCertificate.objects.bulk_create(
            new_certificate_objects,
            batch_size=batch_size,
            ignore_conflicts=True,
        )
        return len(new_certificate_objects)

    def _migrate_program_certificates(self, conn, options):
        """
        Migrate program certificates from edX to MITx Online. Create ProgramEnrollment
        and ProgramCertificate instances.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)

        cur = conn.cursor()

        query = (
            f"SELECT * FROM {_warehouse_table('edxorg_to_mitxonline_program_certificates')} "  # noqa: S608
            "WHERE user_mitxonline_id IS NOT NULL AND program_id IS NOT NULL "
            "AND certificate_page_revision_id IS NOT NULL "
        )

        if limit is not None:
            query += f" LIMIT {int(limit)}"

        cur.execute(query)
        columns = [desc[0] for desc in cur.description]

        total_enrollments = 0
        total_certificates = 0

        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            rows = [dict(zip(columns, r)) for r in results]

            total_enrollments += self._bulk_create_program_enrollments(rows, batch_size)
            total_certificates += self._bulk_create_program_certificates(
                rows, batch_size
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{total_enrollments} program enrollments created, "
                    f"{total_certificates} program certificates created"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Program certificate migration complete: "
                f"{total_enrollments} enrollments, {total_certificates} certificates"
            )
        )

    def _migrate_entitlements(self, conn, options):  # noqa: PLR0915
        """
        Migrate entitlement from edX to MITx Online. Create program Order instances.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)

        cur = conn.cursor()

        product_content_type_id = ContentType.objects.get_for_model(Product).id

        query = (
            f"SELECT * FROM {_warehouse_table('edxorg_to_mitxonline_program_entitlements')} "  # noqa: S608
            "WHERE order_id IS NULL"
        )

        if limit is not None:
            query += f" LIMIT {int(limit)}"

        cur.execute(query)
        columns = [desc[0] for desc in cur.description]

        created_orders = 0

        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            batch = [dict(zip(columns, r)) for r in results]

            # Bulk-fetch all objects needed by this batch
            program_ids = {row["program_id"] for row in batch}
            user_ids = {row["user_mitxonline_id"] for row in batch}
            product_version_ids = {row["product_version_id"] for row in batch}

            programs = {p.id: p for p in Program.objects.filter(id__in=program_ids)}
            users = {u.id: u for u in User.objects.filter(id__in=user_ids)}
            product_versions = {
                v.id: v for v in Version.objects.filter(id__in=product_version_ids)
            }

            for row in batch:
                try:
                    program = programs.get(row["program_id"])
                    user = users.get(row["user_mitxonline_id"])
                    product_version = product_versions.get(row["product_version_id"])
                    product = (
                        Product.all_objects.filter(
                            id=product_version.field_dict.get("id")
                        ).first()
                        if product_version
                        else None
                    )

                    if not all([program, user, product_version, product]):
                        missing = [
                            name
                            for name, val in [
                                ("program", program),
                                ("user", user),
                                ("product_version", product_version),
                                ("product", product),
                            ]
                            if not val
                        ]
                        self.stdout.write(
                            self.style.ERROR(
                                f"Missing objects {missing} for row: {row}"
                            )
                        )
                        continue

                    if (
                        product_version.content_type_id != product_content_type_id
                        or product_version.field_dict.get("id") != product.id
                    ):
                        self.stdout.write(
                            self.style.ERROR(
                                f"product_version={product_version.id} does not match "
                                f"product={product.id} for row: {row}"
                            )
                        )
                        continue

                    existing_enrollment = ProgramEnrollment.all_objects.filter(
                        user=user,
                        program=program,
                    ).first()
                    if (
                        existing_enrollment
                        and existing_enrollment.enrollment_mode
                        == EDX_ENROLLMENT_VERIFIED_MODE
                    ):
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping order creation: user={user.id} is already enrolled "
                                f"in verified mode for program={program.id}"
                            )
                        )
                        continue

                    with transaction.atomic():
                        order = PendingOrder.create_from_product(
                            product, user, discount=None
                        )
                        # create_from_product always pins the Line to the product's
                        # most recent reversion Version. Re-pin it to the historical
                        # version recorded at the time the entitlement was granted,
                        # so the order reflects the price that was actually paid.
                        line = order.lines.get(
                            purchased_object_id=product.object_id,
                            purchased_content_type_id=product.content_type_id,
                        )
                        if line.product_version_id != product_version.id:
                            line.product_version = product_version
                            line.save(update_fields=["product_version"])
                            # product_version just moved, so the recorded price
                            # is stale.
                            line.record_discounted_unit_price()
                            order.total_price_paid = line.discounted_price
                            order.save(update_fields=["total_price_paid", "updated_on"])
                        fulfill_completed_order(
                            order,
                            payment_data=ZERO_PAYMENT_DATA,
                            already_enrolled=True,
                        )
                        created_orders += 1

                except Exception as e:  # noqa: BLE001
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to migrate entitlement row: {row} error: {e}"
                        )
                    )

        self.stdout.write(self.style.SUCCESS(f"Created {created_orders} Orders"))

    @staticmethod
    def _upgrade_enrollment_modes(verified_rows, existing_enrollments):
        """
        Upgrade enrollment mode to verified for any existing enrollments whose
        current mode differs. Scoped only to verified rows to avoid downgrading
        enrollments not covered by this migration.
        """
        upgrade_q = Q()
        for row in verified_rows:
            existing_mode = existing_enrollments.get(
                (row["user_mitxonline_id"], row["courserun_id"])
            )
            if (
                existing_mode is not None
                and existing_mode != EDX_ENROLLMENT_VERIFIED_MODE
            ):
                upgrade_q |= Q(
                    user_id=row["user_mitxonline_id"],
                    run_id=row["courserun_id"],
                )
        if upgrade_q:
            CourseRunEnrollment.all_objects.filter(upgrade_q).update(
                enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
            )

    def _repair_user(self, user, repaired_user_ids):
        """Attempt to repair a faulty edX user, skipping if already repaired."""
        if user.id in repaired_user_ids:
            return
        try:
            created_user, created_auth_token = repair_faulty_edx_user(user)
            repaired_user_ids.add(user.id)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Repaired user {user.id}: created_user={created_user}, created_auth_token={created_auth_token}"
                )
            )
        except Exception as e:  # noqa: BLE001
            self.stdout.write(
                self.style.WARNING(
                    f"repair_faulty_edx_user failed for user {user.id}, continuing: {e}"
                )
            )

    def _migrate_enrollments(self, conn, options):  # noqa: PLR0915
        """
        Migrate the edX future enrollments from edX to MITx Online. Create Orders for the verified enrollments.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)
        dry_run = options.get("dry_run")

        cur = conn.cursor()

        query = (
            f"SELECT * FROM {_warehouse_table('edxorg_to_mitxonline_enrollments')} "  # noqa: S608
            "WHERE user_mitxonline_id IS NOT NULL AND courserun_id IS NOT NULL "
            "AND courseruncertificate_created_on IS NULL"
        )
        if limit is not None:
            query += f" LIMIT {int(limit)}"

        cur.execute(query)
        columns = [desc[0] for desc in cur.description]

        total_enrollments = 0
        total_orders = 0
        repaired_user_ids = set()

        GENDER_MAP = {label: code for code, label in GENDER_CHOICES}

        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            rows = [dict(zip(columns, r)) for r in results]

            verified_rows = [
                row
                for row in rows
                if row.get("courserunenrollment_enrollment_mode")
                == EDX_ENROLLMENT_VERIFIED_MODE
            ]

            if dry_run:
                total_enrollments += len(rows)
                total_orders += len(verified_rows)
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY RUN] Would create "
                        f"{total_enrollments} enrollments, "
                        f"{total_orders} verified orders"
                    )
                )
                continue

            all_user_ids = {
                row["user_mitxonline_id"]
                for row in rows
                if row.get("user_mitxonline_id")
            }
            verified_user_ids = {row["user_mitxonline_id"] for row in verified_rows}
            existing_enrollments = {
                (uid, rid): mode
                for uid, rid, mode in CourseRunEnrollment.all_objects.filter(
                    user_id__in=verified_user_ids,
                    run_id__in={row["courserun_id"] for row in verified_rows},
                ).values_list("user_id", "run_id", "enrollment_mode")
            }

            self._upgrade_enrollment_modes(verified_rows, existing_enrollments)
            # Only bulk-create non-verified enrollments here. Verified enrollments
            # are created atomically inside each order's transaction.atomic() block via
            # fulfill_completed_order → create_run_enrollments. Creating them here
            # (before the order loop) leads to inconsistent state if the script is
            # interrupted: the enrollment exists in the DB but no order is ever created.
            non_verified_rows = [
                row
                for row in rows
                if row.get("courserunenrollment_enrollment_mode")
                != EDX_ENROLLMENT_VERIFIED_MODE
            ]
            total_enrollments += self._bulk_create_enrollments(
                non_verified_rows,
                batch_size,
                edx_enrolled=False,
            )

            product_version_ids = {
                row["product_version_id"]
                for row in verified_rows
                if row.get("product_version_id")
            }
            discount_ids = {
                row["discount_id"] for row in verified_rows if row.get("discount_id")
            }

            all_users = {u.id: u for u in User.objects.filter(id__in=all_user_ids)}
            product_versions = {
                v.id: v for v in Version.objects.filter(id__in=product_version_ids)
            }
            discounts = {d.id: d for d in Discount.objects.filter(id__in=discount_ids)}

            verified_courserun_ids = {row["courserun_id"] for row in verified_rows}
            courserun_ct_id = ContentType.objects.get(
                app_label="courses", model="courserun"
            ).pk
            existing_fulfilled_order_pairs = set(
                Order.objects.filter(
                    state=OrderStatus.FULFILLED,
                    purchaser_id__in=verified_user_ids,
                    lines__purchased_content_type_id=courserun_ct_id,
                    lines__purchased_object_id__in=verified_courserun_ids,
                ).values_list("purchaser_id", "lines__purchased_object_id")
            )

            id_row_lookup = {
                row["user_mitxonline_id"]: row
                for row in rows
                if row.get("user_mitxonline_id")
            }
            unsynced_users = [
                user
                for user in all_users.values()
                if not id_row_lookup.get(user.id, {}).get("openedxuser_has_been_synced")
            ]
            self._bulk_create_legal_addresses(unsynced_users, id_row_lookup, batch_size)
            self._bulk_create_user_profiles(
                unsynced_users, id_row_lookup, batch_size, GENDER_MAP
            )
            for user in unsynced_users:
                self._repair_user(user, repaired_user_ids)

            for row in verified_rows:
                try:
                    if (
                        row["user_mitxonline_id"],
                        row["courserun_id"],
                    ) in existing_fulfilled_order_pairs:
                        continue

                    user = all_users.get(row["user_mitxonline_id"])
                    product_version = product_versions.get(
                        row.get("product_version_id")
                    )
                    product = (
                        Product.all_objects.filter(
                            id=product_version.field_dict.get("id")
                        ).first()
                        if product_version
                        else None
                    )
                    discount = discounts.get(row.get("discount_id"))

                    if not all([user, product_version, product]):
                        missing = [
                            name
                            for name, val in [
                                ("user", user),
                                ("product_version", product_version),
                                ("product", product),
                            ]
                            if not val
                        ]
                        self.stdout.write(
                            self.style.ERROR(
                                f"Missing objects {missing} for row: {row}"
                            )
                        )
                        continue

                    with transaction.atomic():
                        order = PendingOrder.create_from_product(
                            product, user, discount=discount
                        )
                        fulfill_completed_order(
                            order,
                            payment_data=ZERO_PAYMENT_DATA,
                            already_enrolled=True,
                        )
                        total_orders += 1

                except Exception as e:  # noqa: BLE001
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to create order for enrollment row: {row} error: {e}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Enrollment migration complete: "
                f"{total_enrollments} enrollments, {total_orders} orders"
            )
        )

    @staticmethod
    def _sync_enrollment_status(rows, *, dry_run):
        """
        Set active on the existing course run enrollments to match the rows.

        Returns:
            int: The number of enrollments updated, or that would be updated on a dry run
        """
        updated = 0
        for active in (True, False):
            match = Q()
            for row in rows:
                if bool(row["courserunenrollment_is_active"]) == active:
                    match |= Q(
                        user_id=row["user_mitxonline_id"], run_id=row["courserun_id"]
                    )
            if not match:
                continue
            enrollments = CourseRunEnrollment.all_objects.filter(match).exclude(
                active=active
            )
            updated += (
                enrollments.count()
                if dry_run
                else enrollments.update(active=active, updated_on=now_in_utc())
            )
        return updated

    @staticmethod
    def _sync_grades(rows, batch_size, *, dry_run, call_stack):
        """
        Create the missing grades, and update the existing grades to match the rows.
        A grade that an admin set is not changed.

        Returns:
            tuple: (grades created, grades updated), or the counts a dry run would write
        """
        rows_by_key = {
            (row["user_mitxonline_id"], row["courserun_id"]): row
            for row in rows
            if row["courserungrade_grade"] is not None
        }
        if not rows_by_key:
            return 0, 0

        with transaction.atomic():
            existing = {
                (grade.user_id, grade.course_run_id): grade
                for grade in CourseRunGrade.objects.select_for_update().filter(
                    user_id__in={user_id for user_id, _ in rows_by_key},
                    course_run_id__in={run_id for _, run_id in rows_by_key},
                )
                if (grade.user_id, grade.course_run_id) in rows_by_key
            }
            new_rows = [row for key, row in rows_by_key.items() if key not in existing]
            grades = [grade for grade in existing.values() if not grade.set_by_admin]
            if dry_run:
                return len(new_rows), len(grades)

            # bulk_update skips save_and_log, so the audit rows are written here
            now = now_in_utc()
            audits = []
            for grade in grades:
                row = rows_by_key[(grade.user_id, grade.course_run_id)]
                data_before = grade.to_dict()
                grade.grade = row["courserungrade_grade"]
                grade.passed = bool(row["courserungrade_is_passing"])
                grade.letter_grade = row.get("courserungrade_letter_grade")
                grade.updated_on = now
                audits.append(
                    CourseRunGradeAudit(
                        course_run_grade=grade,
                        acting_user=None,
                        call_stack=call_stack,
                        data_before=data_before,
                        data_after=grade.to_dict(),
                    )
                )
            CourseRunGrade.objects.bulk_update(
                grades, ["grade", "passed", "letter_grade", "updated_on"]
            )
            CourseRunGradeAudit.objects.bulk_create(audits)
            created = Command._bulk_create_grades(new_rows, batch_size)
        return created, len(grades)

    @staticmethod
    def _course_run_certificate_revisions(run_ids):
        revisions = {}
        course_revisions = {}
        for run in CourseRun.all_objects.filter(id__in=run_ids).select_related(
            "course"
        ):
            if run.course_id not in course_revisions:
                course_revisions[run.course_id] = (
                    run.course.get_certificate_page_revision()
                )
            revisions[run.id] = course_revisions[run.course_id]
        return revisions

    @staticmethod
    def _program_certificate_revisions(program_ids):
        return {
            program.id: program.get_certificate_page_revision()
            for program in Program.objects.filter(id__in=program_ids)
        }

    @staticmethod
    def _sync_certificates(rows, columns, revisions, batch_size, *, dry_run):
        """
        Create the missing valid certificates, and set is_revoked on the existing
        certificates to match the rows. A certificate is created only when its
        course or program has a certificate page.

        Args:
            rows (list of dict): The warehouse rows
            columns (_CertificateColumns): The certificate model and its row columns
            revisions (dict): The certificate page revision for each course run or program id
            batch_size (int): Number of objects per bulk query
            dry_run (bool): Count the changes without writing them

        Returns:
            tuple: (certificates created, certificates updated, rows skipped for a
            missing certificate page), or the counts a dry run would write
        """
        rows_by_key = {
            (row["user_mitxonline_id"], row[columns.object_column]): row for row in rows
        }
        if not rows_by_key:
            return 0, 0, 0

        existing = {
            (cert.user_id, getattr(cert, columns.object_field)): cert
            for cert in columns.model.all_objects.filter(
                user_id__in={user_id for user_id, _ in rows_by_key},
                **{
                    f"{columns.object_field}__in": {
                        object_id for _, object_id in rows_by_key
                    }
                },
            )
        }

        now = now_in_utc()
        to_update = []
        to_create = []
        skipped = 0
        for (user_id, object_id), row in rows_by_key.items():
            is_revoked = bool(row[columns.revoked_column])
            cert = existing.get((user_id, object_id))
            if cert is not None:
                if cert.is_revoked != is_revoked:
                    cert.is_revoked = is_revoked
                    cert.updated_on = now
                    to_update.append(cert)
                continue
            if is_revoked:
                continue
            revision = revisions.get(object_id)
            if revision is None:
                skipped += 1
                continue
            to_create.append(
                columns.model(
                    user_id=user_id,
                    **{columns.object_field: object_id},
                    # The source's UUID keeps old certificate links working
                    uuid=row.get(columns.uuid_column) or uuid.uuid4(),
                    issue_date=_warehouse_datetime(row[columns.issued_column]),
                    certificate_page_revision=revision,
                )
            )

        if not dry_run:
            columns.model.all_objects.bulk_update(
                to_update, ["is_revoked", "updated_on"], batch_size=batch_size
            )
            columns.model.all_objects.bulk_create(
                to_create, batch_size=batch_size, ignore_conflicts=True
            )
        return len(to_create), len(to_update), skipped

    def _write_totals(self, totals, *, dry_run):
        counts = ", ".join(
            f"{count} {name}"
            for name, count in totals.items()
            if not name.endswith("skipped")
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Would write: {counts}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Migration complete: {counts}"))

    def _write_certificate_skips(self, skipped, kind):
        if skipped:
            self.stdout.write(
                self.style.ERROR(
                    f"Skipped {skipped} {kind} certificates: the {kind} has no live "
                    "certificate page"
                )
            )

    def _migrate_course_enrollments(self, conn, options):
        """
        Migrate the course run enrollments, grades and certificates of a platform in
        the mitxonline_migration_* tables. Each row's migration_status says what to do:
        new creates the enrollment with its grade and certificate, status_changed
        sets the enrollment's active status, grade_changed sets the grade, and
        certificate_changed creates the certificate or sets its revoked status.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)
        dry_run = options.get("dry_run")
        platform = options["platform"]
        call_stack = f"migrate_edx_data --platform {platform} --type course_enrollments"

        table, conditions = _platform_table("course_enrollments", platform)
        # The ids stay null until the user and the run are in MITx Online
        conditions += ["user_mitxonline_id IS NOT NULL", "courserun_id IS NOT NULL"]
        courserun_filter, params = self._courserun_filter(options)
        if courserun_filter:
            conditions.append(courserun_filter)

        cur = conn.cursor()
        cur.execute(_select_query(table, conditions, limit), params)
        columns = [desc[0] for desc in cur.description]

        totals = defaultdict(int)
        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            rows_by_status = defaultdict(list)
            for result in results:
                row = dict(zip(columns, result))
                rows_by_status[row["migration_status"]].append(row)
            new_rows = rows_by_status["new"]

            # edx_enrolled=True keeps retry_failed_edx_enrollments from pushing
            # the migrated enrollments to Open edX
            totals["enrollments created"] += (
                len(new_rows)
                if dry_run
                else self._bulk_create_enrollments(new_rows, batch_size)
            )
            totals["enrollments updated"] += self._sync_enrollment_status(
                rows_by_status["status_changed"], dry_run=dry_run
            )

            created, updated = self._sync_grades(
                new_rows + rows_by_status["grade_changed"],
                batch_size,
                dry_run=dry_run,
                call_stack=call_stack,
            )
            totals["grades created"] += created
            totals["grades updated"] += updated

            certificate_rows = [
                row
                for row in new_rows
                if row["courseruncertificate_created_on"] is not None
            ] + rows_by_status["certificate_changed"]
            created, updated, skipped = self._sync_certificates(
                certificate_rows,
                COURSE_RUN_CERTIFICATE_COLUMNS,
                self._course_run_certificate_revisions(
                    {row["courserun_id"] for row in certificate_rows}
                ),
                batch_size,
                dry_run=dry_run,
            )
            totals["certificates created"] += created
            totals["certificates updated"] += updated
            totals["certificates skipped"] += skipped

        self._write_totals(totals, dry_run=dry_run)
        self._write_certificate_skips(totals["certificates skipped"], "course")

    def _migrate_platform_program_certificates(self, conn, options):
        """
        Migrate the program enrollments and certificates of a platform in the
        mitxonline_migration_* tables. A new row creates the program enrollment and
        the certificate. A certificate_changed row sets the certificate's revoked
        status.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)
        dry_run = options.get("dry_run")

        table, conditions = _platform_table("program_certificates", options["platform"])
        # The ids stay null until the user and the program are in MITx Online
        conditions += ["user_mitxonline_id IS NOT NULL", "program_id IS NOT NULL"]

        cur = conn.cursor()
        cur.execute(_select_query(table, conditions, limit))
        columns = [desc[0] for desc in cur.description]

        totals = defaultdict(int)
        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            rows = [dict(zip(columns, r)) for r in results]
            new_rows = [row for row in rows if row["migration_status"] == "new"]

            totals["program enrollments created"] += (
                len(new_rows)
                if dry_run
                else self._bulk_create_program_enrollments(new_rows, batch_size)
            )
            created, updated, skipped = self._sync_certificates(
                rows,
                PROGRAM_CERTIFICATE_COLUMNS,
                self._program_certificate_revisions(
                    {row["program_id"] for row in rows}
                ),
                batch_size,
                dry_run=dry_run,
            )
            totals["program certificates created"] += created
            totals["program certificates updated"] += updated
            totals["program certificates skipped"] += skipped

        self._write_totals(totals, dry_run=dry_run)
        self._write_certificate_skips(totals["program certificates skipped"], "program")

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--use-default-signatory",
            action="store_true",
            help="Use default signatory for certificate pages for testing purposes, which is the first signatory.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit the number of rows processed from the warehouse (for testing purposes)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of warehouse rows to process per batch (default: 1000). The whole result is read into memory first.",
        )
        parser.add_argument(
            "--platform",
            choices=PLATFORMS,
            default=PLATFORM_EDXORG,
            help=(
                "The platform to migrate from (default: edxorg). edxorg reads the "
                "edxorg_to_mitxonline_* tables. The other platforms read their rows "
                "of the mitxonline_migration_* tables."
            ),
        )
        types_by_platform = {
            platform: list(self._migrations(platform)) for platform in PLATFORMS
        }
        parser.add_argument(
            "--type",
            choices=list(
                dict.fromkeys(t for types in types_by_platform.values() for t in types)
            ),
            default="course_runs",
            help=(
                "Choose which migration to run (default: course_runs). "
                + "; ".join(
                    f"{platform}: {', '.join(types)}"
                    for platform, types in types_by_platform.items()
                )
            ),
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--courserun-readable-ids",
            type=str,
            help="Comma-separated list of course run readable IDs to migrate",
        )

    def _migrations(self, platform):
        """The progress message and the method of each migration type of the platform"""
        if platform == PLATFORM_EDXORG:
            return {
                "course_runs": (
                    "Migrating the edX course runs ...",
                    self._migrate_course_runs,
                ),
                "users": ("Migrating the edX users ...", self._migrate_users),
                "course_certificates": (
                    "Migrating the edX course enrollments, grades and certificates ...",
                    self._migrate_course_certificates,
                ),
                "program_certificates": (
                    "Migrating the edX program enrollments and certificates ...",
                    self._migrate_program_certificates,
                ),
                "entitlements": (
                    "Migrating the edX entitlements to program orders and enrollments ...",
                    self._migrate_entitlements,
                ),
                "future_enrollments": (
                    "Migrating the edX future enrollments  ...",
                    self._migrate_enrollments,
                ),
                "repair_migrated_profiles": (
                    "Repairing LegalAddress/UserProfile rows missed by a "
                    "historical bug in the users migration ...",
                    self._repair_migrated_user_profiles,
                ),
                "letter_grades": (
                    "Backfilling edX.org letter grades ...",
                    self._backfill_letter_grades,
                ),
            }
        return {
            "course_runs": (
                f"Migrating the {platform} course runs ...",
                self._migrate_course_runs,
            ),
            "users": (f"Migrating the {platform} users ...", self._migrate_users),
            "course_enrollments": (
                f"Migrating the {platform} course enrollments, grades and "
                "certificates ...",
                self._migrate_course_enrollments,
            ),
            "program_certificates": (
                f"Migrating the {platform} program enrollments and certificates ...",
                self._migrate_platform_program_certificates,
            ),
        }

    def handle(self, *args, **options):  # pylint: disable=unused-argument # noqa: ARG002
        platform = options["platform"]
        migrate_type = options.get("type")
        migrations = self._migrations(platform)
        if migrate_type not in migrations:
            msg = (
                f"--type {migrate_type} is not available for --platform {platform}. "
                f"Choose one of: {', '.join(migrations)}"
            )
            raise CommandError(msg)

        conn = self._connect_to_warehouse()

        message, migrate = migrations[migrate_type]
        self.stdout.write(message)
        migrate(conn, options)
