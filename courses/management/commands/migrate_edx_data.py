from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from trino.auth import BasicAuthentication
from trino.dbapi import connect

from cms.api import create_default_courseware_page
from cms.models import CertificatePage, SignatoryPage
from courses.models import (
    Course,
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
    Department,
)
from users.models import GENDER_CHOICES, LegalAddress, User, UserProfile


class Command(BaseCommand):
    help = (
        "Migrate the edX data via Trino from the data platform to the corresponding models in MITx Online "
        "e.g Course, CourseRun, CoursePage CertificatePage, etc."
    )

    def _connect_to_trino(self):
        try:
            conn = connect(
                host=settings.TRINO_HOST,
                port=settings.TRINO_PORT,
                user=settings.TRINO_USER,
                auth=BasicAuthentication(settings.TRINO_USER, settings.TRINO_PASSWORD),
                catalog=settings.TRINO_CATALOG,
                schema="ol_warehouse_production_migration",
            )
            self.stdout.write(self.style.SUCCESS("Successfully connected to Trino"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to connect to Trino: {e}"))
            raise
        else:
            return conn

    def _create_course(self, row):
        """
        Create a new Course instance or get an existing one using data from the row.

        Args:
            row (dict): Dictionary containing course data from Trino

        Returns:
            tuple: Tuple containing (Course instance, boolean indicating if created)
            - Course instance: The created or retrieved Course model instance
            - boolean: True if a new course was created, False if existing was retrieved
        """
        department, _ = Department.objects.get_or_create(
            name=row.get("department_name")
        )

        course, created = Course.objects.get_or_create(
            readable_id=row.get("course_readable_id"),
            defaults={
                "title": row.get("course_title"),
                "readable_id": row.get("course_readable_id"),
                "live": False,
            },
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

    def _create_course_run(self, course, row):
        """
        Create a new CourseRun instance for the given course using data from row.

        Args:
            course (Course): Course model instance to create the run for
            row (dict): Dictionary containing course run data from Trino

        Returns:
            tuple: Tuple containing (CourseRun instance, boolean indicating if created)
        """
        course_run, created_run = CourseRun.objects.get_or_create(
            courseware_id=row.get("courseware_id"),
            defaults={
                "course": course,
                "run_tag": row.get("run_tag"),
                "start_date": row.get("start_date"),
                "end_date": row.get("end_date"),
                "enrollment_start": row.get("enrollment_start"),
                "enrollment_end": row.get("enrollment_end"),
                "title": row.get("courserun_title"),
                "live": True,
                "is_self_paced": row.get("is_self_paced"),
            },
        )
        return course_run, created_run

    def _get_signatories(self, signatory_list, use_default_signatory):
        """
        Get SignatoryPage based on the provided list of names or use the default signatory.

        Args:
            signatory_list (list): List of signatory names
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
            for name in signatory_list
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

        cur = conn.cursor()

        query = "SELECT * FROM edxorg_to_mitxonline_course_runs"
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]

        course_success_count = 0
        run_success_count = 0

        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            for result in results:
                row = dict(zip(columns, result))
                # Skip rows with no department courses or any course with no certificates
                if (
                    not row.get("department_name")
                    and row.get("mitxonline_course_id") is None
                ) or (
                    row.get("certificate_count") is None
                    or int(row.get("certificate_count", 0)) < 1
                ):
                    continue

                signatories = self._get_signatories(
                    row.get("signatory_names") or [], use_default_signatory
                )

                if not signatories and row.get("mitxonline_course_id") is None:
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

                course_run, run_created = self._create_course_run(course, row)
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
        return User.objects.bulk_create(
            new_users, batch_size=batch_size, ignore_conflicts=True
        )

    @staticmethod
    def _bulk_create_legal_addresses(created_users, row_lookup, batch_size):
        """
        Create legal addresses in bulk for the created users.
        """
        legal_addresses = []
        for user in created_users:
            user_data = row_lookup.get(user.email)
            if not user_data:
                continue
            country = user_data.get("user_address_country")
            if not country:
                continue
            legal_addresses.append(LegalAddress(user=user, country=country))
        if legal_addresses:
            LegalAddress.objects.bulk_create(legal_addresses, batch_size=batch_size)

    @staticmethod
    def _bulk_create_user_profiles(created_users, row_lookup, batch_size, gender_map):
        """
        Create user profiles in bulk for the created users.
        """

        user_profiles = []
        for user in created_users:
            user_data = row_lookup.get(user.email)
            if not user_data:
                continue
            gender = user_data.get("user_gender")
            birth_year = user_data.get("user_birth_year")
            if not gender and not birth_year:
                continue
            user_profiles.append(
                UserProfile(
                    user=user, year_of_birth=birth_year, gender=gender_map.get(gender)
                )
            )
        if user_profiles:
            UserProfile.objects.bulk_create(user_profiles, batch_size=batch_size)

    def _migrate_users(self, conn, options):
        """
        Migrate users from edX to MITx Online. Create User, LegalAddress, and UserProfile instances.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)

        cur = conn.cursor()

        query = "SELECT * FROM edxorg_to_mitxonline_users"
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]

        # e.g. {"Male": "m", "Female": "f"}
        GENDER_MAP = {label: code for code, label in GENDER_CHOICES}

        user_creation_count = 0
        while True:
            results = cur.fetchmany(batch_size)
            if not results:
                break

            rows = [dict(zip(columns, r)) for r in results]

            row_lookup = {
                row["user_email"]: row for row in rows if row.get("user_email")
            }
            emails = list(row_lookup.keys())

            existing_emails = set(
                User.objects.filter(
                    Q(username__in=emails) | Q(email__in=emails)
                ).values_list("email", flat=True)
            )

            created_users = self._bulk_create_users(rows, existing_emails, batch_size)
            user_creation_count += len(created_users)

            self._bulk_create_legal_addresses(created_users, row_lookup, batch_size)
            self._bulk_create_user_profiles(
                created_users, row_lookup, batch_size, GENDER_MAP
            )

        self.stdout.write(self.style.SUCCESS(f"{user_creation_count} users created"))

    @staticmethod
    def _bulk_create_enrollments(rows, batch_size):
        new_enrollment_objects = [
            CourseRunEnrollment(
                user_id=row["user_mitxonline_id"],
                run_id=row["courserun_id"],
                enrollment_mode=row["courserunenrollment_enrollment_mode"],
                active=True,
            )
            for row in rows
        ]
        if not new_enrollment_objects:
            return 0

        CourseRunEnrollment.objects.bulk_create(
            new_enrollment_objects, batch_size=batch_size, ignore_conflicts=True
        )
        return len(new_enrollment_objects)

    @staticmethod
    def _bulk_create_grades(rows, batch_size):
        new_grade_objects = [
            CourseRunGrade(
                user_id=row["user_mitxonline_id"],
                course_run_id=row["courserun_id"],
                grade=row["courserungrade_grade"],
                passed=row["courserungrade_is_passing"],
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
                issue_date=row["courseruncertificate_created_on"],
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

    def _migrate_certificates(self, conn, options):
        """
        Migrate certificates from edX to MITx Online. Create CourseRunEnrollment, CourseRunGrade,
        and CourseRunCertificate instances.
        """
        limit = options.get("limit")
        batch_size = options.get("batch_size", 1000)
        dry_run = options.get("dry_run")
        courserun_readable_ids = [
            readable_id.strip()
            for readable_id in (options.get("courserun_readable_ids") or "").split(",")
            if readable_id
        ] or None

        cur = conn.cursor()

        query = (
            "SELECT * FROM edxorg_to_mitxonline_enrollments "
            "WHERE user_mitxonline_id IS NOT NULL AND courserun_id IS NOT NULL"
        )
        if courserun_readable_ids:
            placeholders = [
                f"'{readable_id}'" for readable_id in courserun_readable_ids
            ]
            query += f" AND courserun_readable_id IN ({','.join(placeholders)})"

        if limit is not None:
            query += f" LIMIT {int(limit)}"

        cur.execute(query)
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

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--use-default-signatory",
            action="store_true",
            help="Use default signatory for certificate pages for testing purposes, which is the first signatory.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit the number of rows processed from Trino (for testing purposes)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of rows to fetch per batch from Trino (default: 1000)",
        )
        parser.add_argument(
            "--type",
            choices=["course_runs", "users", "certificates"],
            default="course_runs",
            help="Choose which migration to run: course_runs, users (default: course_runs)",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--courserun-readable-ids",
            type=str,
            help="Comma-separated list of course run readable IDs to migrate",
        )

    def handle(self, *args, **options):  # pylint: disable=unused-argument # noqa: ARG002
        conn = self._connect_to_trino()

        migrate_type = options.get("type")

        if migrate_type == "course_runs":
            self.stdout.write("Migrating the edX course runs ...")
            self._migrate_course_runs(conn, options)

        if migrate_type == "users":
            self.stdout.write("Migrating the edX users ...")
            self._migrate_users(conn, options)

        if migrate_type == "certificates":
            self.stdout.write(
                "Migrating the edX enrollments, grades and certificates ..."
            )
            self._migrate_certificates(conn, options)
