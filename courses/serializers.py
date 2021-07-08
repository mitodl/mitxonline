"""
Course model serializers
"""
from urllib.parse import urljoin

from django.conf import settings
from django.templatetags.static import static
from rest_framework import serializers

from courses import models


def _get_thumbnail_url(page):
    """
    Get the thumbnail URL or else return a default image URL.

    Args:
        page (cms.models.ProductPage): A product page

    Returns:
        str:
            A page URL
    """
    relative_url = (
        page.thumbnail_image.file.url
        if page
        and page.thumbnail_image
        and page.thumbnail_image.file
        and page.thumbnail_image.file.url
        else static("images/mit-dome.png")
    )
    return urljoin(settings.SITE_BASE_URL, relative_url)


class BaseCourseSerializer(serializers.ModelSerializer):
    """Basic course model serializer"""

    class Meta:
        model = models.Course
        fields = ["id", "title", "readable_id"]


class BaseCourseRunSerializer(serializers.ModelSerializer):
    """Minimal CourseRun model serializer"""

    class Meta:
        model = models.CourseRun
        fields = [
            "title",
            "start_date",
            "end_date",
            "enrollment_start",
            "enrollment_end",
            "expiration_date",
            "courseware_url",
            "courseware_id",
            "run_tag",
            "id",
        ]


class CourseRunSerializer(BaseCourseRunSerializer):
    """CourseRun model serializer"""

    class Meta:
        model = models.CourseRun
        fields = BaseCourseRunSerializer.Meta.fields


class CourseSerializer(serializers.ModelSerializer):
    """Course model serializer - also serializes child course runs"""

    courseruns = serializers.SerializerMethodField()
    next_run_id = serializers.SerializerMethodField()
    topics = serializers.SerializerMethodField()

    def get_next_run_id(self, instance):
        """Get next run id"""
        run = instance.first_unexpired_run
        return run.id if run is not None else None

    def get_courseruns(self, instance):
        """Unexpired and unenrolled course runs"""
        all_runs = self.context.get("all_runs", False)
        if all_runs:
            active_runs = instance.unexpired_runs
        else:
            user = self.context["request"].user if "request" in self.context else None
            active_runs = (
                instance.available_runs(user)
                if user and user.is_authenticated
                else instance.unexpired_runs
            )
        return [
            CourseRunSerializer(instance=run, context=self.context).data
            for run in active_runs
            if run.live
        ]

    def get_topics(self, instance):
        """List topics of a course"""
        return sorted(
            [{"name": topic.name} for topic in instance.topics.all()],
            key=lambda topic: topic["name"],
        )

    class Meta:
        model = models.Course
        fields = [
            "id",
            "title",
            "readable_id",
            "courseruns",
            "next_run_id",
            "topics",
        ]


class CourseRunDetailSerializer(serializers.ModelSerializer):
    """CourseRun model serializer - also serializes the parent Course"""

    course = BaseCourseSerializer(read_only=True)

    class Meta:
        model = models.CourseRun
        fields = [
            "course",
            "title",
            "start_date",
            "end_date",
            "enrollment_start",
            "enrollment_end",
            "expiration_date",
            "courseware_url",
            "courseware_id",
            "id",
        ]


class BaseProgramSerializer(serializers.ModelSerializer):
    """Basic program model serializer"""

    class Meta:
        model = models.Program
        fields = ["title", "readable_id", "id"]


class ProgramSerializer(serializers.ModelSerializer):
    """Program model serializer"""

    courses = serializers.SerializerMethodField()
    start_date = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    enrollment_start = serializers.SerializerMethodField()
    topics = serializers.SerializerMethodField()

    def get_courses(self, instance):
        """Serializer for courses"""
        return CourseSerializer(
            instance.courses.filter(live=True).order_by("position_in_program"),
            many=True,
        ).data

    def get_start_date(self, instance):
        """
        start_date is the starting date for the earliest live course run for all courses in a program

        Returns:
            datetime: The starting date
        """
        return (
            models.CourseRun.objects.filter(course__program=instance, live=True)
            .order_by("start_date")
            .values_list("start_date", flat=True)
            .first()
        )

    def get_end_date(self, instance):
        """
        end_date is the end date for the latest live course run for all courses in a program.

        Returns:
            datetime: The ending date
        """
        return (
            models.CourseRun.objects.filter(course__program=instance, live=True)
            .order_by("end_date")
            .values_list("end_date", flat=True)
            .last()
        )

    def get_enrollment_start(self, instance):
        """
        enrollment_start is first date where enrollment starts for any live course run
        """
        return (
            models.CourseRun.objects.filter(course__program=instance, live=True)
            .order_by("enrollment_start")
            .values_list("enrollment_start", flat=True)
            .first()
        )

    def get_topics(self, instance):
        """List all topics in all courses in the program"""
        topics = (
            models.CourseTopic.objects.filter(course__program=instance)
            .values("name")
            .distinct("name")
        )
        return list(topics)

    class Meta:
        model = models.Program
        fields = [
            "title",
            "readable_id",
            "id",
            "courses",
            "start_date",
            "end_date",
            "enrollment_start",
            "topics",
        ]


class CourseRunEnrollmentSerializer(serializers.ModelSerializer):
    """CourseRunEnrollment model serializer"""

    run = CourseRunDetailSerializer(read_only=True)

    class Meta:
        model = models.CourseRunEnrollment
        fields = ["run"]


class ProgramEnrollmentSerializer(serializers.ModelSerializer):
    """ProgramEnrollmentSerializer model serializer"""

    program = BaseProgramSerializer(read_only=True)
    course_run_enrollments = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        assert (
            "context" in kwargs and "course_run_enrollments" in kwargs["context"]
        ), "An iterable of course run enrollments must be passed in the context (key: course_run_enrollments)"
        super().__init__(*args, **kwargs)

    def get_course_run_enrollments(self, instance):
        """Returns a serialized list of course run enrollments that belong to this program (in position order)"""
        return CourseRunEnrollmentSerializer(
            sorted(
                (
                    enrollment
                    for enrollment in self.context["course_run_enrollments"]
                    if enrollment.run.course.program_id == instance.program.id
                ),
                key=lambda enrollment: enrollment.run.course.position_in_program,
            ),
            many=True,
        ).data

    class Meta:
        model = models.ProgramEnrollment
        fields = [
            "id",
            "program",
            "course_run_enrollments",
        ]
