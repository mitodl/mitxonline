from django.conf import settings
from django.core.management.base import BaseCommand
from trino.auth import BasicAuthentication
from trino.dbapi import connect

from cms.api import create_default_courseware_page
from cms.models import CertificatePage, SignatoryPage
from courses.models import Course, CourseRun, Department


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
                    row.get("signatory_names", []), use_default_signatory
                )

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

    def handle(self, *args, **options):  # pylint: disable=unused-argument # noqa: ARG002
        conn = self._connect_to_trino()

        self._migrate_course_runs(conn, options)
