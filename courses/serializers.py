"""
Course model serializers
"""
import logging
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ObjectDoesNotExist
from django.templatetags.static import static
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from cms.models import CoursePage
from cms.serializers import CoursePageSerializer
from courses import models
from courses.api import create_run_enrollments
from courses.constants import CONTENT_TYPE_MODEL_COURSE, CONTENT_TYPE_MODEL_PROGRAM
from courses.utils import get_program_certificate_by_enrollment
from ecommerce.models import Product
from ecommerce.serializers import BaseProductSerializer, ProductFlexibilePriceSerializer
from flexiblepricing.api import is_courseware_flexible_price_approved
from main import features
from main.serializers import StrictFieldsSerializer
from main.settings import AUTH_USER_MODEL
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE
from users.models import User
from users.serializers import UserSerializer

logger = logging.getLogger(__name__)


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

    type = serializers.SerializerMethodField(read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("include_page_fields") or not hasattr(instance, "page"):
            return data
        return {**data, **CoursePageSerializer(instance=instance.page).data}

    @staticmethod
    def get_type(obj):
        return CONTENT_TYPE_MODEL_COURSE

    class Meta:
        model = models.Course
        fields = [
            "id",
            "title",
            "readable_id",
            "type",
        ]


class ProductRelatedField(serializers.RelatedField):
    """serializer for the Product generic field"""

    def to_representation(self, instance):
        serializer = ProductFlexibilePriceSerializer(
            instance=instance, context=self.context
        )
        return serializer.data


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
            "upgrade_deadline",
            "is_upgradable",
            "run_tag",
            "id",
        ]


class CourseRunSerializer(BaseCourseRunSerializer):
    """CourseRun model serializer"""

    products = ProductRelatedField(many=True, queryset=Product.objects.all())
    page = serializers.SerializerMethodField()
    approved_flexible_price_exists = serializers.SerializerMethodField()

    class Meta:
        model = models.CourseRun
        fields = BaseCourseRunSerializer.Meta.fields + [
            "products",
            "page",
            "approved_flexible_price_exists",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context and self.context.get("include_enrolled_flag"):
            return {
                **data,
                **{
                    "is_enrolled": getattr(instance, "user_enrollments", 0) > 0,
                    "is_verified": getattr(instance, "verified_enrollments", 0) > 0,
                },
            }
        return data

    def get_page(self, instance):
        try:
            return CoursePageSerializer(
                instance=CoursePage.objects.filter(course=instance.course).get()
            ).data
        except ObjectDoesNotExist:
            return None

    def get_approved_flexible_price_exists(self, instance):
        # Get the User object if it exists.
        user = self.context["request"].user if "request" in self.context else None

        # Check for an approved flexible price record if the
        # user exists and has an ID (not an Anonymous user).
        # Otherwise return False.
        flexible_price_exists = (
            is_courseware_flexible_price_approved(
                instance, self.context["request"].user
            )
            if user and user.id
            else False
        )
        return flexible_price_exists


class CourseSerializer(BaseCourseSerializer):
    """Course model serializer - also serializes child course runs"""

    courseruns = serializers.SerializerMethodField()
    next_run_id = serializers.SerializerMethodField()
    topics = serializers.SerializerMethodField()
    page = serializers.SerializerMethodField()

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

    def get_page(self, instance):
        return (
            CoursePageSerializer(
                instance=CoursePage.objects.filter(course=instance).get()
            ).data
            if CoursePage.objects.filter(course=instance).exists()
            else None
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
            "page",
        ]


class CourseRunDetailSerializer(serializers.ModelSerializer):
    """
    CourseRun model serializer - also serializes the parent Course
    Includes the relevant Page (if there is one) and Products (if they exist,
    just the base product data)
    """

    course = BaseCourseSerializer(read_only=True, context={"include_page_fields": True})
    products = BaseProductSerializer(read_only=True, many=True)
    page = serializers.SerializerMethodField()

    def get_page(self, instance):
        try:
            return CoursePageSerializer(
                instance=CoursePage.objects.filter(course=instance.course).get()
            ).data
        except ObjectDoesNotExist:
            return None

    class Meta:
        model = models.CourseRun
        fields = [
            "course_number",
            "course",
            "title",
            "start_date",
            "end_date",
            "enrollment_start",
            "enrollment_end",
            "expiration_date",
            "certificate_available_date",
            "courseware_url",
            "courseware_id",
            "upgrade_deadline",
            "is_upgradable",
            "is_self_paced",
            "id",
            "products",
            "page",
        ]


class BaseProgramSerializer(serializers.ModelSerializer):
    """Basic program model serializer"""

    type = serializers.SerializerMethodField(read_only=True)

    @staticmethod
    def get_type(obj):
        return CONTENT_TYPE_MODEL_PROGRAM

    class Meta:
        model = models.Program
        fields = ["title", "readable_id", "id", "type"]


class ProgramSerializer(serializers.ModelSerializer):
    """Program model serializer"""

    courses = serializers.SerializerMethodField()
    start_date = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    enrollment_start = serializers.SerializerMethodField()
    topics = serializers.SerializerMethodField()
    requirements = serializers.SerializerMethodField()
    req_tree = serializers.SerializerMethodField()

    def get_courses(self, instance):
        """Serializer for courses"""
        return CourseSerializer(
            instance.courses.filter(live=True)
            .order_by("position_in_program")
            .select_related("page"),
            many=True,
            context={"include_page_fields": True},
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

    def _get_nested_requirements(self, node):
        ids = []

        if node.get_children():
            for child in node.get_children():
                if child.node_type == models.ProgramRequirementNodeType.OPERATOR:
                    ids += self._get_nested_requirements(child)
                elif child.course.id is not None:
                    ids.append(child.course.id)

        return ids

    def get_requirements(self, instance):
        formatted_reqs = {"required": [], "electives": []}

        req_root = instance.get_requirements_root()

        if req_root is None:
            return []

        for node in req_root.get_children():
            if node.operator == models.ProgramRequirement.Operator.ALL_OF:
                formatted_reqs["required"] = self._get_nested_requirements(node)
            else:
                formatted_reqs["electives"] = self._get_nested_requirements(node)

        return formatted_reqs

    def get_req_tree(self, instance):
        req_root = instance.get_requirements_root()

        if req_root is None:
            return []

        return ProgramRequirementTreeSerializer(instance=req_root).data

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
            "requirements",
            "req_tree",
        ]


class CourseRunCertificateSerializer(serializers.ModelSerializer):
    """CourseRunCertificate model serializer"""

    class Meta:
        model = models.CourseRunCertificate
        fields = ["uuid", "link"]


class CourseRunGradeSerializer(serializers.ModelSerializer):
    """CourseRunGrade serializer"""

    class Meta:
        model = models.CourseRunGrade
        fields = ["grade", "letter_grade", "passed", "set_by_admin", "grade_percent"]


class CourseRunEnrollmentSerializer(serializers.ModelSerializer):
    """CourseRunEnrollment model serializer"""

    run = CourseRunDetailSerializer(read_only=True)
    run_id = serializers.IntegerField(write_only=True)
    certificate = serializers.SerializerMethodField(read_only=True)
    enrollment_mode = serializers.ChoiceField(
        (EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE), read_only=True
    )
    approved_flexible_price_exists = serializers.SerializerMethodField()
    grades = serializers.SerializerMethodField(read_only=True)

    def create(self, validated_data):
        user = self.context["user"]
        run_id = validated_data["run_id"]
        try:
            run = models.CourseRun.objects.get(id=run_id)
        except models.CourseRun.DoesNotExist:
            raise ValidationError({"run_id": f"Invalid course run id: {run_id}"})
        successful_enrollments, edx_request_success = create_run_enrollments(
            user,
            [run],
            keep_failed_enrollments=features.is_enabled(features.IGNORE_EDX_FAILURES),
        )
        return successful_enrollments

    def get_certificate(self, enrollment):
        """
        Resolve a certificate for this enrollment if it exists
        """
        # When create method is called it returns list object of enrollments
        if isinstance(enrollment, list):
            enrollment = enrollment[0] if enrollment else None

        # No need to include a certificate if there is no corresponding wagtail page
        # to support the render
        try:
            if (
                not enrollment
                or not enrollment.run.course.page
                or not enrollment.run.course.page.certificate_page
            ):
                return None
        except models.Course.page.RelatedObjectDoesNotExist:
            return None

        # Using IDs because we don't need the actual record and this avoids redundant queries
        user_id = enrollment.user_id
        course_run_id = enrollment.run_id
        try:
            return CourseRunCertificateSerializer(
                models.CourseRunCertificate.objects.get(
                    user_id=user_id, course_run_id=course_run_id
                )
            ).data
        except models.CourseRunCertificate.DoesNotExist:
            return None

    def get_approved_flexible_price_exists(self, instance):
        instance_run = instance[0].run if isinstance(instance, list) else instance.run
        instance_user = (
            instance[0].user if isinstance(instance, list) else instance.user
        )
        flexible_price_exists = is_courseware_flexible_price_approved(
            instance_run, instance_user
        )
        return flexible_price_exists

    def get_grades(self, instance):
        instance_run = instance[0].run if isinstance(instance, list) else instance.run
        instance_user = (
            instance[0].user if isinstance(instance, list) else instance.user
        )

        return CourseRunGradeSerializer(
            instance=models.CourseRunGrade.objects.filter(
                user=instance_user, course_run=instance_run
            ).all(),
            many=True,
        ).data

    class Meta:
        model = models.CourseRunEnrollment
        fields = [
            "run",
            "id",
            "run_id",
            "edx_emails_subscription",
            "certificate",
            "enrollment_mode",
            "approved_flexible_price_exists",
            "grades",
        ]


class ProgramCertificateSerializer(serializers.ModelSerializer):
    """ProgramCertificate model serializer"""

    class Meta:
        model = models.ProgramCertificate
        fields = ["uuid", "link"]


class ProgramEnrollmentSerializer(serializers.ModelSerializer):
    """ProgramEnrollmentSerializer model serializer"""

    program = BaseProgramSerializer(read_only=True)
    course_run_enrollments = serializers.SerializerMethodField()
    certificate = serializers.SerializerMethodField(read_only=True)

    def __init__(self, *args, **kwargs):
        assert (
            "context" in kwargs and "course_run_enrollments" in kwargs["context"]
        ), "An iterable of course run enrollments must be passed in the context (key: course_run_enrollments)"
        super().__init__(*args, **kwargs)

    def get_certificate(self, enrollment):
        """
        Resolve a certificate for this enrollment if it exists
        """
        certificate = get_program_certificate_by_enrollment(enrollment)
        if certificate:
            return ProgramCertificateSerializer(certificate).data
        return None

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
            "certificate",
        ]


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


class ProgramRequirementSerializer(StrictFieldsSerializer):
    """Serializer for a ProgramRequirement"""

    id = serializers.IntegerField(required=False, allow_null=True, default=None)
    data = ProgramRequirementDataSerializer()

    def get_fields(self):
        """Override because 'children' is a recursive structure"""
        fields = super().get_fields()
        fields["children"] = ProgramRequirementSerializer(many=True, default=[])
        return fields


class ProgramRequirementTreeSerializer(serializers.ListSerializer):
    """
    Serializer for root nodes of a program requirement tree

    The instance is considered immutable and the data passed in
    is expected to be a list of objects in the structure that ProgramRequirement.load_bulk()
    can consume.
    """

    child = ProgramRequirementSerializer()

    def update(self, instance, validated_data):
        """
        Update the program requirement tree

        This is inspired by the load_bulk method, but that method is an append-only operation and doesn't update existing records
        """
        keep_node_ids = []

        def _get_existing(data):
            node_id = data.get("id", None)
            return (
                models.ProgramRequirement.objects.filter(id=node_id).first()
                if node_id
                else None
            )

        # we'll recursively walk the tree, in practice this is at most 3 deep under instance (OPERATOR -> OPERATOR -> COURSE)
        def _update(parent, children_data):
            last_updated_child = None

            for node_data in children_data:
                parent.refresh_from_db()
                first_child = parent.get_first_child()
                existing_child = _get_existing(node_data)

                data = {
                    **node_data["data"],
                    "program_id": instance.program_id,
                }
                children = node_data.get("children", [])

                if existing_child is None:
                    # we're inserting a new node
                    if last_updated_child is not None:
                        # insert after the last node we updated or inserted
                        last_updated_child = last_updated_child.add_sibling(
                            "right", **data
                        )
                    elif first_child is not None:
                        # otherwise insert as the first sibling
                        last_updated_child = first_child.add_sibling(
                            "first-sibling", **data
                        )
                    else:
                        # insert as a regular child node as there's no children yet
                        last_updated_child = parent.add_child(**data)
                else:
                    # we have an existing node and need to move it and update it
                    if last_updated_child is not None:
                        # place it after the last node we updated
                        existing_child.move(last_updated_child, pos="right")
                    elif first_child is not None:
                        # move it to the first sibling
                        existing_child.move(first_child, "first-sibling")
                    elif parent is not None:
                        # this would only happen if the child is moving form another part of the tree, which
                        # we don't support at the moment but it's here for completeness and future-proofing
                        existing_child.move(parent, "first-child")

                    # since this is an existing node we need to update the props and save
                    for key, value in data.items():
                        setattr(existing_child, key, value)

                    existing_child.save(update_fields=data.keys())

                    last_updated_child = existing_child

                keep_node_ids.append(last_updated_child.id)

                # if the input has children, process those
                if children:
                    _update(last_updated_child, children)

        _update(instance, validated_data)

        # delete all descendants that didn't show up in the input
        instance.get_descendants().exclude(id__in=keep_node_ids).delete()

        instance.refresh_from_db()

        return instance

    @property
    def data(self):
        """Serializes the root node to a bulk dump of the tree"""
        # here we're bypassing Serializer.data implementation because it coerces
        # the to_representation return value into a dict of its keys
        return models.ProgramRequirement.dump_bulk(parent=self.instance, keep_ids=True)


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

        for course in instance.courses.all():
            fmt_course = {
                "title": course.title,
                "id": course.id,
                "readable_id": course.readable_id,
                "reqtype": course.requirement_type,
                "grade": None,
                "certificate": None,
            }

            grade = (
                models.CourseRunGrade.objects.filter(
                    user=user, course_run__course=course
                )
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
