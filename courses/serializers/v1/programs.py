from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from mitol.common.utils import now_in_utc
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from cms.serializers import ProgramPageSerializer
from courses import models
from courses.serializers import get_thumbnail_url, BaseProgramRequirementTreeSerializer
from courses.serializers.v1.departments import DepartmentSerializer
from courses.serializers.v1.courses import CourseWithCourseRunsSerializer, CourseRunEnrollmentSerializer
from courses.serializers.v1.base import CourseRunCertificateSerializer, CourseRunGradeSerializer
from main.serializers import StrictFieldsSerializer
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
from users.models import User


class ProgramSerializer(serializers.ModelSerializer):
    """Program model serializer"""

    courses = serializers.SerializerMethodField()
    requirements = serializers.SerializerMethodField()
    req_tree = serializers.SerializerMethodField()
    page = serializers.SerializerMethodField()
    departments = DepartmentSerializer(many=True, read_only=True)

    def get_courses(self, instance):
        """Serializer for courses"""
        return CourseWithCourseRunsSerializer(
            [course[0] for course in instance.courses if course[0].live],
            many=True,
            context={"include_page_fields": True},
        ).data

    def get_requirements(self, instance):
        return {
            "required": [course.id for course in instance.required_courses],
            "electives": [course.id for course in instance.elective_courses],
        }

    def get_req_tree(self, instance):
        req_root = instance.get_requirements_root()

        if req_root is None:
            return []

        return ProgramRequirementTreeSerializer(instance=req_root).data

    def get_page(self, instance):
        if hasattr(instance, "page"):
            return ProgramPageSerializer(instance.page).data
        else:
            return {"feature_image_src": get_thumbnail_url(None)}

    class Meta:
        model = models.Program
        fields = [
            "title",
            "readable_id",
            "id",
            "courses",
            "requirements",
            "req_tree",
            "page",
            "program_type",
            "departments",
            "live",
        ]


class FullProgramSerializer(ProgramSerializer):
    """Adds more data to the ProgramSerializer."""

    start_date = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    enrollment_start = serializers.SerializerMethodField()

    def get_start_date(self, instance):
        """
        start_date is the starting date for the earliest live course run for all courses in a program

        Returns:
            datetime: The starting date
        """
        courses_in_program = [course[0] for course in instance.courses]
        return (
            models.CourseRun.objects.filter(course__in=courses_in_program, live=True)
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
        courses_in_program = [course[0] for course in instance.courses]
        return (
            models.CourseRun.objects.filter(course__in=courses_in_program, live=True)
            .order_by("end_date")
            .values_list("end_date", flat=True)
            .last()
        )

    def get_enrollment_start(self, instance):
        """
        enrollment_start is first date where enrollment starts for any live course run
        """
        courses_in_program = [course[0] for course in instance.courses]
        return (
            models.CourseRun.objects.filter(course__in=courses_in_program, live=True)
            .order_by("enrollment_start")
            .values_list("enrollment_start", flat=True)
            .first()
        )

    class Meta(ProgramSerializer.Meta):
        fields = ProgramSerializer.Meta.fields + [
            "title",
            "readable_id",
            "id",
            "courses",
            "num_courses",
            "requirements",
            "req_tree",
        ]


class ProgramCertificateSerializer(serializers.ModelSerializer):
    """ProgramCertificate model serializer"""

    class Meta:
        model = models.ProgramCertificate
        fields = ["uuid", "link"]


class UserProgramEnrollmentDetailSerializer(serializers.Serializer):
    program = ProgramSerializer()
    enrollments = CourseRunEnrollmentSerializer(many=True)
    certificate = serializers.SerializerMethodField(read_only=True)

    def get_certificate(self, user_program_enrollment):
        """
        Resolve a certificate for this enrollment if it exists
        """
        certificate = user_program_enrollment.get("certificate")
        return ProgramCertificateSerializer(certificate).data if certificate else None


class ProgramRequirementDataSerializer(StrictFieldsSerializer):
    """Serializer for ProgramRequirement data"""

    node_type = serializers.ChoiceField(
        choices=(
            models.ProgramRequirementNodeType.OPERATOR,
            models.ProgramRequirementNodeType.COURSE,
        )
    )
    course = serializers.CharField(source="course_id", allow_null=True, default=None)
    program = serializers.CharField(source="program_id", required=False)
    title = serializers.CharField(allow_null=True, default=None)
    operator = serializers.CharField(allow_null=True, default=None)
    operator_value = serializers.CharField(allow_null=True, default=None)
    elective_flag = serializers.BooleanField(allow_null=True, default=False)


class ProgramRequirementSerializer(StrictFieldsSerializer):
    """Serializer for a ProgramRequirement"""

    id = serializers.IntegerField(required=False, allow_null=True, default=None)
    data = ProgramRequirementDataSerializer()

    def get_fields(self):
        """Override because 'children' is a recursive structure"""
        fields = super().get_fields()
        fields["children"] = ProgramRequirementSerializer(many=True, default=[])
        return fields


class ProgramRequirementTreeSerializer(BaseProgramRequirementTreeSerializer):

    child = ProgramRequirementSerializer()


class PartnerSchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PartnerSchool
        fields = "__all__"


class LearnerProgramRecordShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.LearnerProgramRecordShare
        fields = "__all__"


class LearnerRecordSerializer(serializers.BaseSerializer):
    """
    Gathers the various data needed to display the learner's program record.
    Pass the program you want the record for and attach the learner via context
    object.
    """

    def to_representation(self, instance):
        """
        Returns formatted data.

        Args:
        - instance (Program): The program to retrieve data for.
        """
        user = None

        if "request" in self.context:
            if not isinstance(self.context["request"].user, AnonymousUser):
                user = self.context["request"].user

        if "user" in self.context and isinstance(self.context["user"], User):
            user = self.context["user"]

        if user is None:
            raise ValidationError("Valid user object not found")

        courses = []
        for course, requirement_type in instance.courses:
            fmt_course = {
                "title": course.title,
                "id": course.id,
                "readable_id": course.readable_id,
                "reqtype": requirement_type,
                "grade": None,
                "certificate": None,
            }
            runs_ids = models.CourseRunCertificate.objects.filter(
                user=user, course_run__course=course, is_revoked=False
            ).values_list("course_run__id", flat=True)

            if not runs_ids:
                # if there are no certificates then show verified enrollment grades that either
                # certificate available date has passed or course has ended if no certificate available date
                runs_ids = models.CourseRunEnrollment.objects.filter(
                    Q(user=user)
                    & Q(run__course=course)
                    & Q(enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE)
                    & Q(change_status=None)
                    & (
                        Q(run__certificate_available_date__lt=now_in_utc())
                        | (
                            Q(run__certificate_available_date=None)
                            & Q(run__end_date__lt=now_in_utc())
                        )
                    )
                ).values_list("run__id", flat=True)

            grade = (
                models.CourseRunGrade.objects.filter(user=user, course_run__in=runs_ids)
                .order_by("-grade")
                .first()
            )

            if grade is not None:
                grade.grade = round(grade.grade, 2)
                fmt_course["grade"] = CourseRunGradeSerializer(grade).data

            certificate = (
                models.CourseRunCertificate.objects.filter(
                    user=user, course_run__course=course, is_revoked=False
                )
                .order_by("-created_on")
                .first()
            )

            if certificate is not None:
                fmt_course["certificate"] = CourseRunCertificateSerializer(
                    certificate
                ).data

            courses.append(fmt_course)

        shares = models.LearnerProgramRecordShare.objects.filter(
            user=user, program=instance, is_active=True
        ).all()

        output = {
            "user": {
                "name": user.name,
                "email": user.email,
                "username": user.username,
            },
            "program": {
                "title": instance.title,
                "readable_id": instance.readable_id,
                "courses": courses,
                "requirements": ProgramRequirementTreeSerializer(
                    instance.requirements_root
                ).data,
            },
            "sharing": LearnerProgramRecordShareSerializer(shares, many=True).data
            if "anonymous_pull" not in self.context
            else [],
            "partner_schools": PartnerSchoolSerializer(
                models.PartnerSchool.objects.all(), many=True
            ).data
            if "anonymous_pull" not in self.context
            else [],
        }

        return output
