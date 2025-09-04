from django.conf import settings
from django.core.management.base import BaseCommand
from trino.auth import BasicAuthentication
from trino.dbapi import connect

from cms.api import create_default_courseware_page
from courses.models import Course, CourseRun, Department


class Command(BaseCommand):
    help = "Migrate edx courserun data from Trino in data platform to Course/CourseRun models"

    def handle(self, *args, **options):
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
            self.stdout.write(self.style.ERROR(f"Failed to connect to Trino: {e!s}"))
            raise

        cur = conn.cursor()
        cur.execute("SELECT * FROM edxorg_to_mitxonline_course_runs")
        columns = [desc[0] for desc in cur.description]

        course_success_count = 0
        run_success_count = 0
        while True:
            rows = cur.fetchmany(100)
            if not rows:
                break

            for row in rows:
                row_dict = dict(zip(columns, row))
                # Skip rows with no department courses or any course with no certificates
                if (
                    not row_dict.get("department_name")
                    and row_dict.get("mitxonline_course_id") is None
                ) or (
                    row_dict.get("certificate_count") is None
                    or int(row_dict.get("certificate_count", 0)) < 1
                ):
                    continue

                department, _ = Department.objects.get_or_create(
                    name=row_dict.get("department_name")
                )

                (course, created) = Course.objects.get_or_create(
                    readable_id=row_dict.get("course_readable_id"),
                    defaults={
                        "title": row_dict.get("course_title"),
                        "readable_id": row_dict.get("course_readable_id"),
                        "live": False,
                    },
                )
                course.departments.add(department)
                course.save()

                if created:
                    course_success_count += 1
                    try:
                        create_default_courseware_page(course, live=False)
                    except Exception as e:  # noqa: BLE001
                        self.stdout.write(
                            self.style.ERROR(
                                f"Could not create CMS page {course.readable_id}, skipping it: {e}"
                            )
                        )

                course_run, created_run = CourseRun.objects.get_or_create(
                    courseware_id=row_dict.get("courseware_id"),
                    defaults={
                        "course": course,
                        "run_tag": row_dict.get("run_tag"),
                        "start_date": row_dict.get("start_date"),
                        "end_date": row_dict.get("end_date"),
                        "enrollment_start": row_dict.get("enrollment_start"),
                        "enrollment_end": row_dict.get("enrollment_end"),
                        "title": row_dict.get("courserun_title"),
                        "live": True,
                        "is_self_paced": row_dict.get("is_self_paced"),
                    },
                )

                if created_run:
                    run_success_count += 1

        self.stdout.write(self.style.SUCCESS(f"{course_success_count} courses created"))
        self.stdout.write(
            self.style.SUCCESS(f"{run_success_count} course runs created")
        )
