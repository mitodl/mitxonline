from django.conf import settings
from django.core.management.base import BaseCommand
from trino.auth import BasicAuthentication
from trino.dbapi import connect

from cms.api import create_default_courseware_page
from cms.models import CertificatePage, SignatoryPage
from courses.models import Course, CourseRun, Department


class Command(BaseCommand):
    help = (
        "Migrate the EdX courses from Trino in data platform to Course/CourseRun models"
    )

    def _connect_to_trino(self):
        try:
            conn = connect(
                host=settings.TRINO_HOST,
                port=settings.TRINO_PORT,
                user=settings.TRINO_USER,
                auth=BasicAuthentication(settings.TRINO_USER, settings.TRINO_PASSWORD),
                catalog=settings.TRINO_CATALOG,
                schema=settings.TRINO_SCHEMA,
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

    def _create_course_certificate_page(self, course_page, course_title, signatory):
        """
        Create a certificate page for a course and associate it with a signatory.

        Args:
            course_page: The course page to create the certificate page under
            course_title: Title of the course to use in certificate
            signatory: The SignatoryPage instance to associate with the certificate

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

        if signatory:
            # Create the signatory block with only required fields
            signatory_block = {"type": "signatory", "value": signatory.id}
            certificate_page.signatories = [signatory_block]

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

    def handle(self, *args, **options):  # pylint: disable=unused-argument # noqa: ARG002
        conn = self._connect_to_trino()

        cur = conn.cursor()
        cur.execute("SELECT * FROM edxorg_to_mitxonline_course_runs")
        columns = [desc[0] for desc in cur.description]

        course_success_count = 0
        run_success_count = 0

        # Assign a default signatory for the certificate page when creating new courses
        signatory = SignatoryPage.objects.filter(name="Dimitris Bertsimas").first()

        while True:
            results = cur.fetchmany(100)
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

                (course, course_created) = self._create_course(row)

                if course_created:
                    try:
                        course_page = create_default_courseware_page(course, live=False)
                        self._create_course_certificate_page(
                            course_page, row.get("course_title"), signatory
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
