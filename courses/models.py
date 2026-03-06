# ruff: noqa: TD002, TD003, FIX002
"""
Course models
"""

import logging
import uuid
from decimal import ROUND_HALF_EVEN, Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.text import slugify
from django_countries.fields import CountryField
from mitol.common.models import TimestampedModel, TimestampedModelQuerySet
from mitol.common.utils.datetime import now_in_utc
from mitol.openedx.utils import get_course_number
from modelcluster.fields import ParentalKey
from prefetch import Prefetcher, PrefetchManagerMixin, PrefetchQuerySet
from treebeard.mp_tree import MP_Node
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.fields import RichTextField
from wagtail.models import ClusterableModel, Orderable, Page, Revision

from courses.constants import (
    AVAILABILITY_ANYTIME,
    AVAILABILITY_CHOICES,
    ENROLL_CHANGE_STATUS_CHOICES,
    ENROLLABLE_ITEM_ID_SEPARATOR,
    SYNCED_COURSE_RUN_FIELD_MSG,
)
from main.models import AuditableModel, AuditModel, ValidateOnSaveMixin
from main.utils import serialize_model_object
from openedx.constants import EDX_DEFAULT_ENROLLMENT_MODE, EDX_ENROLLMENTS_PAID_MODES

User = get_user_model()

log = logging.getLogger(__name__)


class ActiveCertificates(models.Manager):
    """
    Return the active certificates only
    """

    def get_queryset(self):
        """
        Returns:
            QuerySet: queryset for un-revoked certificates
        """
        return super().get_queryset().filter(is_revoked=False)


class ProgramQuerySet(models.QuerySet):  # pylint: disable=missing-docstring
    def live(self):
        """Applies a filter for Programs with live=True"""
        return self.filter(live=True)

    def with_text_id(self, text_id):
        """Applies a filter for the Program's readable_id"""
        return self.filter(readable_id=text_id)


class CourseQuerySet(models.QuerySet):  # pylint: disable=missing-docstring
    def live(self):
        """Applies a filter for Courses with live=True"""
        return self.filter(live=True)

    def courses_in_program(self, program):
        """Return a list of courses that are required by a given program"""
        return self.filter(in_programs__program=program)


class CourseRunQuerySet(models.QuerySet):  # pylint: disable=missing-docstring
    def exclude_b2b(self):
        """Exclude B2B course runs."""

        return self.filter(b2b_contract__isnull=True)

    def live(self, *, include_b2b=False):
        """Applies a filter for Course runs with live=True"""

        queryset = self.filter(live=True)
        return queryset if include_b2b else queryset.filter(b2b_contract__isnull=True)

    def available(self, *, include_b2b=False):
        """Applies a filter for Course runs with end_date in future"""

        q_filter = models.Q(end_date__isnull=True) | models.Q(end_date__gt=now_in_utc())

        if include_b2b:
            return self.filter(q_filter)
        return self.filter(b2b_contract__isnull=True).filter(q_filter)

    def enrollable(self, enrollment_end_date=None):
        """
        Applies a filter for Course runs that are open for enrollment.

        This mirrors the logic from CourseRun.is_enrollable property but allows
        for custom enrollment_end_date parameter.

        Args:
            enrollment_end_date: datetime, the date to check for enrollment end.
                               If None, uses current time.
        """
        return self.filter(self.get_enrollable_filter(enrollment_end_date))

    def unenrollable(self):
        """Applies a filter for Course runs that are closed for enrollment."""

        now = now_in_utc()
        return self.filter(
            models.Q(live=False)
            | models.Q(start_date__isnull=True)
            | (models.Q(enrollment_end__lte=now) | models.Q(enrollment_start__gt=now))
        )

    @classmethod
    def get_enrollable_filter(cls, enrollment_end_date=None):
        """
        Returns Q filter for enrollable course runs.

        This allows other functions to use the same enrollment logic
        while composing it with additional filters.

        Args:
            enrollment_end_date: datetime, the date to check for enrollment end.
                               If None, uses current time.

        Returns:
            Q: Django Q filter for enrollable course runs
        """

        now = now_in_utc()
        if enrollment_end_date is None:
            enrollment_end_date = now

        return (
            # Check if enrollment has not ended
            (
                models.Q(enrollment_end__isnull=True)
                | models.Q(enrollment_end__gt=enrollment_end_date)
            )
            # Ensure enrollment has started
            & models.Q(enrollment_start__isnull=False)
            & models.Q(enrollment_start__lte=now)
            # Course run must be live
            & models.Q(live=True)
            # Course run must have started
            & models.Q(start_date__isnull=False)
        )

    def with_text_id(self, text_id):
        """Applies a filter for the CourseRun's courseware_id"""
        return self.filter(courseware_id=text_id)


class CoursesTopicQuerySet(models.QuerySet):
    """
    Custom QuerySet for `CoursesTopic`
    """

    def parent_topics(self):
        """
        Applies a filter for course topics with parent=None
        """
        return self.filter(parent__isnull=True).order_by("name")

    def parent_topic_names(self):
        """
        Returns a list of all parent topic names.
        """
        return list(self.parent_topics().values_list("name", flat=True))


class EnrollmentQuerySet(TimestampedModelQuerySet, PrefetchQuerySet):
    """QuerySet for Enrollment models"""


class EnrollmentManager(
    models.Manager.from_queryset(EnrollmentQuerySet), PrefetchManagerMixin
):
    """Base manager class for enrollments"""


class ActiveEnrollmentManager(EnrollmentManager):
    """Query manager for active enrollment model objects"""

    def get_queryset(self):
        """Manager queryset"""
        return super().get_queryset().filter(active=True)


detail_path_char_pattern = r"\w\-+:\."
validate_url_path_field = RegexValidator(
    rf"^[{detail_path_char_pattern}]+$",
    f"This field is used to produce URL paths. It must contain only characters that match this pattern: [{detail_path_char_pattern}]",
)


class DepartmentQuerySet(TimestampedModelQuerySet):
    """QuerySet for Department"""

    def for_serialization(self):
        return self.prefetch_related(
            Prefetch(
                "courses",
                queryset=Course.objects.annotate(
                    has_enrollable_courserun=Exists(
                        CourseRun.objects.enrollable().filter(course_id=OuterRef("pk"))
                    ),
                )
                .filter(
                    live=True,
                    page__live=True,
                    has_enrollable_courserun=True,
                )
                .only("id"),
            ),
            Prefetch(
                "programs",
                queryset=Program.objects.filter(live=True, page__live=True).only("id"),
            ),
        )


class Department(TimestampedModel):
    """
    Departments.
    """

    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(max_length=128, unique=True)

    objects = DepartmentQuerySet.as_manager()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class EnrollmentMode(models.Model):
    """Enrollment modes for the courseware object."""

    mode_slug = models.CharField(
        max_length=255, blank=True, default=EDX_DEFAULT_ENROLLMENT_MODE, unique=True
    )
    mode_display_name = models.CharField(
        max_length=255, blank=True, default=EDX_DEFAULT_ENROLLMENT_MODE
    )
    requires_payment = models.BooleanField(default=False, blank=True)

    def __str__(self):
        return self.mode_display_name

    def save(self, *args, **kwargs):
        """If display name isn't set, make it the slug."""
        if not self.mode_display_name:
            self.mode_display_name = self.mode_slug

        super().save(*args, **kwargs)


class Program(TimestampedModel, ValidateOnSaveMixin):
    """Model for a course program"""

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["live", "id"]),
            models.Index(fields=["readable_id"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    objects = ProgramQuerySet.as_manager()
    title = models.CharField(max_length=255)
    readable_id = models.CharField(
        max_length=255, unique=True, validators=[validate_url_path_field]
    )
    live = models.BooleanField(default=False, db_index=True)
    program_type = models.CharField(  # noqa: DJ001
        max_length=255,
        default="Series",
        blank=True,
        null=True,
    )
    departments = models.ManyToManyField(
        Department, blank=False, related_name="programs"
    )
    availability = models.CharField(
        choices=AVAILABILITY_CHOICES, default=AVAILABILITY_ANYTIME, max_length=255
    )
    enrollment_start = models.DateTimeField(null=True, blank=True, db_index=True)
    enrollment_end = models.DateTimeField(null=True, blank=True, db_index=True)
    enrollment_modes = models.ManyToManyField(
        EnrollmentMode, blank=True, related_name="+"
    )
    start_date = models.DateTimeField(null=True, blank=True, db_index=True)
    end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    b2b_only = models.BooleanField(
        default=False, help_text="Indicates if the program is B2B only"
    )
    products = GenericRelation("ecommerce.Product", related_query_name="programs")

    @cached_property
    def page(self):
        """Gets the associated ProgramPage"""
        return getattr(self, "programpage", None)

    @cached_property
    def num_courses(self):
        """Gets the number of courses in this program"""
        return len(self.courses)

    @property
    def first_unexpired_run(self):
        """Gets the earliest unexpired CourseRun"""
        return (
            CourseRun.objects.filter(course__in_programs__program=self)
            .order_by("start_date")
            .first()
        )

    @property
    def next_starting_run(self):
        """Gets the earliest starting CourseRun"""
        return (
            CourseRun.objects.filter(
                course__in_programs__program=self,
                start_date__gt=now_in_utc(),
                live=True,
            )
            .order_by("start_date")
            .first()
        )

    @property
    def text_id(self):
        """Gets the readable_id"""
        return self.readable_id

    @property
    def related_programs_qs(self):
        """
        Returns a list of programs related to this one. Returns a QuerySet.

        Returns:
        - QuerySet: RelatedPrograms that are related to this program, in either the first or second position
        """

        the_jam = RelatedProgram.objects.filter(
            Q(first_program=self) | Q(second_program=self)
        )

        return the_jam  # noqa: RET504

    @property
    def related_programs(self):
        """
        Returns a list of programs related to this one. Returns a flat list,
        not a QuerySet.

        Returns:
        - List(Program): programs that are related to this program, in either the first or second position
        """

        program_list = []

        for related_program in self.related_programs_qs.all().iterator():
            if related_program.first_program == self:
                program_list.append(related_program.second_program)
            else:
                program_list.append(related_program.first_program)

        return program_list

    def add_related_program(self, program):
        """
        Adds a related program record for the specified program. If there's
        already a related program, then this will return the existing relation.

        Args:
        - Program: the program to add a relation for
        Returns:
        - RelatedProgram; the relation
        """

        related_program_existence_qs = self.related_programs_qs.filter(
            Q(first_program=program) | Q(second_program=program)
        )

        if not related_program_existence_qs.exists():
            return RelatedProgram.objects.create(
                first_program=self, second_program=program
            )

        return related_program_existence_qs.get()

    @cached_property
    def requirements_root(self):
        return self.get_requirements_root()

    def get_requirements_root(self, *, for_update=False):
        """The root of the requirements tree"""
        query = ProgramRequirement.get_root_nodes().filter(program=self)
        if for_update:
            query = query.select_for_update()

        return query.first()

    def _add_course_node(self, node_type, min_courses=1):
        """
        Adds the given course node type to the root of the requirements tree, or
        returns the existing node if there is one.

        Arguments:
        - node_type (str): one of the ProgramRequirement.Operator constants
        - min_courses (int): number of courses to require (for electives)
        Returns:
        - ProgramRequirement: the node you requested
        """
        node = (
            self.get_requirements_root()
            .get_children()
            .filter(operator=node_type)
            .first()
        )

        if node is None:
            if node_type == ProgramRequirement.Operator.MIN_NUMBER_OF:
                node = self.get_requirements_root().add_child(
                    node_type=ProgramRequirementNodeType.OPERATOR,
                    operator=node_type,
                    title="Elective Courses",
                    operator_value=min_courses,
                    elective_flag=True,
                )
            else:
                node = self.get_requirements_root().add_child(
                    node_type=ProgramRequirementNodeType.OPERATOR,
                    operator=node_type,
                    title="Required Courses",
                )

            node.save()
            node.refresh_from_db()

        return node

    def add_requirement(self, requirement):
        """Makes the specified course a required course"""
        if isinstance(requirement, Course):
            self.get_requirements_root().get_children().filter(
                course=requirement
            ).delete()

            new_req = self._add_course_node(
                ProgramRequirement.Operator.ALL_OF
            ).add_child(course=requirement, node_type=ProgramRequirementNodeType.COURSE)
        elif isinstance(requirement, Program):
            self.get_requirements_root().get_children().filter(
                required_program=requirement
            ).delete()

            new_req = self._add_course_node(
                ProgramRequirement.Operator.ALL_OF
            ).add_child(
                required_program=requirement,
                node_type=ProgramRequirementNodeType.PROGRAM,
            )

        return new_req

    def add_elective(self, course):
        """Makes the specified course an elective course"""
        self.get_requirements_root().get_children().filter(course=course).delete()

        new_req = self._add_course_node(
            ProgramRequirement.Operator.MIN_NUMBER_OF
        ).add_child(course=course, node_type=ProgramRequirementNodeType.COURSE)

        return new_req  # noqa: RET504

    def add_program_requirement(self, required_program):
        """Makes the specified program a required program"""
        self.get_requirements_root().get_children().filter(
            required_program=required_program
        ).delete()

        new_req = self._add_course_node(ProgramRequirement.Operator.ALL_OF).add_child(
            required_program=required_program,
            node_type=ProgramRequirementNodeType.PROGRAM,
        )

        return new_req  # noqa: RET504

    def add_program_elective(self, required_program):
        """Makes the specified program an elective program"""
        self.get_requirements_root().get_children().filter(
            required_program=required_program
        ).delete()

        new_req = self._add_course_node(
            ProgramRequirement.Operator.MIN_NUMBER_OF
        ).add_child(
            required_program=required_program,
            node_type=ProgramRequirementNodeType.PROGRAM,
        )

        return new_req  # noqa: RET504

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not ProgramRequirement.get_root_nodes().filter(program=self).exists():
            ProgramRequirement.add_root(
                program=self, node_type=ProgramRequirementNodeType.PROGRAM_ROOT.value
            )

    @property
    def courses_qset(self):
        """
        Returns a QuerySet of the related courses for this program, using the
        requirements tree.
        """

        return (
            Course.objects.filter(in_programs__program=self)
            .distinct()
            .prefetch_related("courseruns", "departments")
        )

    def _get_operator_course_requirements(self, main_ops):
        """
        Helper method to fetch all course requirements under operator nodes.

        Args:
            main_ops: List of main operator nodes

        Returns:
            QuerySet of ProgramRequirement objects for courses
        """
        if not main_ops:
            return ProgramRequirement.objects.none()

        path_q = Q()
        for op in main_ops:
            path_q |= Q(path__startswith=op.path)

        return (
            ProgramRequirement.objects.filter(
                program__id=self.id,
                node_type=ProgramRequirementNodeType.COURSE,
            )
            .filter(path_q)
            .prefetch_related(
                "course",
                Prefetch(
                    "course__courseruns",
                    queryset=CourseRun.objects.filter(live=True).order_by("id"),
                ),
                "course__courseruns__enrollment_modes",
            )
        )

    def _process_course_requirements(self, course_reqs, path_to_operator):
        """
        Helper method to process course requirements and categorize them.

        Args:
            course_reqs: QuerySet of course requirements
            path_to_operator: Dict mapping operator paths to operators

        Returns:
            Dict with processed course data
        """
        courses = []
        required_courses = []
        elective_courses = []
        required_title = "Required Courses"
        elective_title = "Elective Courses"
        minimum_elective_requirement = None

        # First, check all operators for titles and minimum elective requirements
        for op in path_to_operator.values():
            # Store titles from actual operator nodes
            if not op.elective_flag and required_title == "Required Courses":
                required_title = op.title or required_title
            elif op.elective_flag and elective_title == "Elective Courses":
                elective_title = op.title or elective_title
                if (
                    op.is_min_number_of_operator
                    and minimum_elective_requirement is None
                ):
                    minimum_elective_requirement = (
                        int(op.operator_value) if op.operator_value else None
                    )

        for req in course_reqs:
            if not req.course:
                continue

            # Find which operator this requirement belongs to
            parent_op = self._find_parent_operator(req, path_to_operator)
            if parent_op is None:
                continue

            requirement_type = (
                "Required Courses"
                if not parent_op.elective_flag
                else "Elective Courses"
            )

            # Build course tuples and separate lists
            course_tuple = (req.course, requirement_type)
            courses.append(course_tuple)

            if not parent_op.elective_flag:
                required_courses.append(req.course)
            else:
                elective_courses.append(req.course)

        return {
            "courses": courses,
            "required_courses": required_courses,
            "elective_courses": elective_courses,
            "required_title": required_title,
            "elective_title": elective_title,
            "minimum_elective_requirement": minimum_elective_requirement,
        }

    def _find_parent_operator(self, req, path_to_operator):
        """
        Helper method to find the parent operator for a course requirement.

        Args:
            req: Course requirement object
            path_to_operator: Dict mapping operator paths to operators

        Returns:
            Parent operator object or None
        """
        for op_path, op in path_to_operator.items():
            if req.path.startswith(op_path) and req.path != op_path:
                return op
        return None

    @cached_property
    def _courses_with_requirements_data(self):
        """
        Internal method that efficiently fetches course requirements data.

        Returns:
        - dict: Contains 'courses', 'required_courses', 'elective_courses',
                'required_title', 'elective_title', and 'minimum_elective_requirement'
        """
        # Get all operator nodes at depth 2 (direct children of root)
        main_ops = ProgramRequirement.objects.filter(program=self, depth=2).all()

        if not main_ops:
            return {
                "courses": [],
                "required_courses": [],
                "elective_courses": [],
                "required_title": "Required Courses",
                "elective_title": "Elective Courses",
                "minimum_elective_requirement": None,
            }

        # Fetch all course requirements efficiently
        course_reqs = self._get_operator_course_requirements(main_ops)

        # Create a mapping from path prefix to operator for efficient lookup
        path_to_operator = {op.path: op for op in main_ops}

        # Process and categorize the requirements
        return self._process_course_requirements(course_reqs, path_to_operator)

    @property
    def courses(self):
        """
        Returns the courses associated with this program via the requirements
        tree. This returns a flat list, not a QuerySet.

        Returns:
        - list of tuple (Course, string): courses that are either requirements or electives, plus the requirement type
        """
        return self._courses_with_requirements_data["courses"]

    @cached_property
    def required_courses(self) -> list:
        """
        Returns just the courses under the "Required Courses" node.
        """
        return self._courses_with_requirements_data["required_courses"]

    @cached_property
    def required_title(self):
        """
        Returns the title of the requirements node that holds the required
        courses (e.g. the one that has elective_flag = False).
        """
        return self._courses_with_requirements_data["required_title"]

    @cached_property
    def elective_courses(self) -> list:
        """
        Returns just the courses under the "Elective Courses" node.
        """
        return self._courses_with_requirements_data["elective_courses"]

    @property
    def required_programs(self):
        """
        Returns the programs that are required by this program.

        Returns:
        - list of Program: programs that are requirements
        """
        return [
            req.required_program
            for req in ProgramRequirement.objects.filter(
                program=self,
                node_type=ProgramRequirementNodeType.PROGRAM,
                required_program__isnull=False,
            )
            .select_related("required_program")
            .all()
            if not req.get_parent().elective_flag
        ]

    @property
    def elective_programs(self):
        """
        Returns the programs that are electives for this program.

        Returns:
        - list of Program: programs that are electives
        """
        return [
            req.required_program
            for req in ProgramRequirement.objects.filter(
                program=self,
                node_type=ProgramRequirementNodeType.PROGRAM,
                required_program__isnull=False,
            )
            .select_related("required_program")
            .all()
            if req.get_parent().elective_flag
        ]

    def __str__(self):
        title = f"{self.readable_id} | {self.title}"
        return title if len(title) <= 100 else title[:97] + "..."  # noqa: PLR2004

    @cached_property
    def elective_title(self):
        """
        Returns the title of the requirements node that holds the elective
        courses (e.g. the one that has elective_flag = True).
        """
        return self._courses_with_requirements_data["elective_title"]

    @cached_property
    def minimum_elective_courses_requirement(self):
        """
        Returns the (int) value defined for the minimum number of elective courses required to be completed by the Program

        Returns:
            int: Minimum number of elective courses required to be completed by the Program.
                Returns None, if no value is defined or elective node is absent.
        """
        return self._courses_with_requirements_data["minimum_elective_requirement"]

    @property
    def is_program(self):
        """Flag to indicate if this is a program"""
        return True

    @property
    def is_run(self):
        """Flag to indicate if this is a run"""
        return False

    @property
    def collections(self):
        """
        Returns a list of ProgramCollections that this program is part of.

        Returns:
            list: List of ProgramCollection objects
        """
        return list(
            ProgramCollection.objects.filter(
                collection_items__program__id=self.id
            ).distinct()
        )


class RelatedProgram(TimestampedModel, ValidateOnSaveMixin):
    """
    Keeps track of which programs are related for financial assistance reasons.

    For financial assistance, a learner may apply for aid for a specific
    program. If the program has RelatedPrograms, the financial assistance
    request should apply to all of them (so, an approval for DEDP Internal
    Development also grants aid in DEDP Public Policy).
    """

    first_program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="+"
    )
    second_program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="+"
    )

    def __str__(self):
        return f"Related Programs {self.first_program.readable_id}<-->{self.second_program.readable_id}"


class ProgramRun(TimestampedModel, ValidateOnSaveMixin):
    """Model for program run (a specific offering of a program, used for sales purposes)"""

    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="programruns"
    )
    run_tag = models.CharField(max_length=10, validators=[validate_url_path_field])
    start_date = models.DateTimeField(null=True, blank=True, db_index=True)
    end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    products = GenericRelation("ecommerce.Product", related_query_name="programruns")

    class Meta:
        unique_together = ("program", "run_tag")

    @property
    def title(self):
        """Return the program title"""
        return self.program.title

    @property
    def readable_id(self):
        """
        Returns the program's readable id with this program run's suffix

        Returns:
            str: The program's readable id with a program run suffix
        """
        return ENROLLABLE_ITEM_ID_SEPARATOR.join(
            [self.program.readable_id, self.run_tag]
        )

    @property
    def is_program(self):
        """Flag to indicate if this is a program"""
        return True

    @property
    def is_run(self):
        """Flag to indicate if this is a run"""
        return True

    def __str__(self):
        return f"{self.program.readable_id} | {self.program.title}"


class CoursesTopic(TimestampedModel):
    """
    Topics for all courses (e.g. "History")
    """

    name = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="child_topics",
    )
    objects = CoursesTopicQuerySet.as_manager()

    class Meta:
        unique_together = ("name", "parent")
        ordering = ["parent__name", "name"]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} -> {self.name}"
        return self.name


class Course(TimestampedModel, ValidateOnSaveMixin):
    """Model for a course"""

    class Meta:
        ordering = ["readable_id"]

    objects = CourseQuerySet.as_manager()
    title = models.CharField(max_length=255)
    readable_id = models.CharField(
        max_length=255, unique=True, validators=[validate_url_path_field]
    )
    live = models.BooleanField(default=False, db_index=True)
    departments = models.ManyToManyField(
        Department, blank=False, related_name="courses"
    )
    flexible_prices = GenericRelation(
        "flexiblepricing.FlexiblePrice",
        object_id_field="courseware_object_id",
        content_type_field="courseware_content_type",
    )
    tiers = GenericRelation(
        "flexiblepricing.FlexiblePriceTier",
        object_id_field="courseware_object_id",
        content_type_field="courseware_content_type",
    )

    @cached_property
    def course_number(self):
        """
        Returns:
            str: Course number (last part of readable_id, after the final +)
        """
        return self.readable_id.split("+")[-1]

    @cached_property
    def page(self):
        """Gets the associated CoursePage"""
        return getattr(self, "coursepage", None)

    @cached_property
    def active_products(self):
        """
        Gets active products for the first unexpired courserun for this course

        Returns:
        - ProductsQuerySet
        """
        relevant_run = self.first_unexpired_run

        return (
            relevant_run.products.filter(is_active=True).all() if relevant_run else None
        )

    @cached_property
    def first_unexpired_run(self):
        """
        Gets the first unexpired/enrollable CourseRun associated with this Course. Giving preference to
        non-archived courses

        Returns:
            CourseRun or None: An unexpired/enrollable course run
        """
        # Use the CourseRunQuerySet.enrollable() method to eliminate code duplication
        # First try to find non-past enrollable runs (end_date is None or in the future)
        best_run = (
            self.courseruns.filter(b2b_contract__isnull=True)
            .enrollable()
            .filter(Q(end_date__isnull=True) | Q(end_date__gt=now_in_utc()))
            .order_by("start_date")
            .first()
        )

        # If no non-past runs found, look for any enrollable runs (including archived)
        if best_run is None:
            best_run = (
                self.courseruns.filter(b2b_contract__isnull=True)
                .enrollable()
                .order_by("start_date")
                .first()
            )

        return best_run

    @cached_property
    def include_in_learn_catalog(self):
        """
        Return true if the course should be included in the Learn catalog.

        This is controlled in the CoursePage for the course, and will default
        to False if there isn't one.
        """

        return getattr(self.page, "include_in_learn_catalog", False)

    @cached_property
    def ingest_content_files_for_ai(self):
        """
        Return true if the course's content files should be ingested.

        This is controlled in the CoursePage for the course, and will default
        to False if there isn't one.
        """

        return getattr(self.page, "ingest_content_files_for_ai", False)

    def get_first_unexpired_b2b_run(self, user_contracts):
        """
        Gets the first unexpired/enrollable CourseRun associated with both this
        Course and the user's specified contracts.

        First means in start date order ascending.

        Args:
        - user_contracts (list of int): the current user's contracts

        Returns:
            CourseRun or None: An unexpired/enrollable course run
        """
        # Use the CourseRunQuerySet.enrollable() method to eliminate code duplication
        # First try to find non-past enrollable runs (end_date is None or in the future)
        best_run = (
            self.courseruns.filter(b2b_contract__in=user_contracts)
            .enrollable()
            .filter(Q(end_date__isnull=True) | Q(end_date__gt=now_in_utc()))
            .order_by("start_date")
            .first()
        )

        # If no non-past runs found, look for any enrollable runs (including archived)
        if best_run is None:
            best_run = (
                self.courseruns.filter(b2b_contract__in=user_contracts)
                .enrollable()
                .order_by("start_date")
                .first()
            )

        return best_run

    @cached_property
    def programs(self):
        """
        Returns a list of Programs which have this Course (self) as a dependency.

        Returns:
            list: List of Programs this Course is a requirement or elective for.
        """
        programs_containing_course = (
            ProgramRequirement.objects.filter(
                node_type=ProgramRequirementNodeType.COURSE, course=self
            )
            .all()
            .distinct("program_id")
            .order_by("program_id")
            .values_list("program_id", flat=True)
        )

        return [  # noqa: C416
            program
            for program in Program.objects.filter(
                pk__in=[id for id in programs_containing_course]  # noqa: A001, C416
            ).all()
        ]

    def is_country_blocked(self, user):
        """
        Check if the user is from a blocked country for this course

        Args:
            user (users.models.User): The user to check available runs for.

        Returns:
            bool: True if user is from blocked country
        """
        return self.blocked_countries.filter(
            country=user.legal_address.country
        ).exists()

    @property
    def is_program(self):
        """Flag to indicate if this is a program"""
        return False

    @property
    def is_run(self):
        """Flag to indicate if this is a run"""
        return False

    def __str__(self):
        title = f"{self.readable_id} | {self.title}"
        return title if len(title) <= 100 else title[:97] + "..."  # noqa: PLR2004


class CourseRun(TimestampedModel):
    """Model for a single run/instance of a course"""

    objects = CourseRunQuerySet.as_manager()
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="courseruns", db_index=True
    )
    title = models.CharField(
        max_length=255,
        help_text=f"The title of the course. {SYNCED_COURSE_RUN_FIELD_MSG}",
    )
    courseware_id = models.CharField(max_length=255, unique=True)
    run_tag = models.TextField(
        max_length=100,
        help_text="A string that identifies the set of runs that this run belongs to (example: 'R2')",
    )
    has_courseware_url = models.BooleanField(
        default=True,
        help_text="Whether this course run should expose a courseware URL. Set to False for test/placeholder runs.",
    )
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=f"The day the course begins. {SYNCED_COURSE_RUN_FIELD_MSG}",
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=f"The last day the course is active. {SYNCED_COURSE_RUN_FIELD_MSG}",
    )
    certificate_available_date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=f"The day certificates should be available to users. {SYNCED_COURSE_RUN_FIELD_MSG}",
    )
    enrollment_start = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=f"The first day students can enroll. {SYNCED_COURSE_RUN_FIELD_MSG}",
    )
    enrollment_end = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=f"The last day students can enroll. {SYNCED_COURSE_RUN_FIELD_MSG}",
    )
    expiration_date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="The date beyond which the learner should not see link to this course run on their dashboard.",
    )
    upgrade_deadline = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="The date beyond which the learner can not enroll in paid course mode.",
    )

    live = models.BooleanField(default=False, db_index=True)
    is_self_paced = models.BooleanField(default=False)
    products = GenericRelation(
        "ecommerce.Product", related_query_name="courserunproducts"
    )
    enrollment_modes = models.ManyToManyField(
        EnrollmentMode, blank=True, related_name="+"
    )

    b2b_contract = models.ForeignKey(
        "b2b.ContractPage",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="course_runs",
    )
    is_source_run = models.BooleanField(
        default=False,
        help_text='Designate this run as a "source" run for contract re-runs of the course.',
    )

    class Meta:
        unique_together = ("course", "courseware_id", "run_tag")

    @property
    def is_past(self):
        """
        Checks if the course run in the past

        Returns:
            boolean: True if course run has ended

        """
        if not self.end_date:
            return False
        return self.end_date < now_in_utc()

    @property
    def is_in_progress(self) -> bool:
        """
        Returns True if the course run has started and has not yet ended
        """
        # Course must have started
        if not self.start_date:
            return False

        now = now_in_utc()

        # Course hasn't started yet
        if self.start_date > now:
            return False

        # Course has ended
        return not (self.end_date and self.end_date <= now)

    @property
    def is_upgradable(self):
        """
        Checks if the course can be upgraded
        A null value means that the upgrade window is always open
        """
        return (
            self.live is True
            and (
                self.upgrade_deadline is None or (self.upgrade_deadline > now_in_utc())
            )
            and self.products.count() > 0
        )

    @cached_property
    def is_enrollable(self):
        """
        Determines if a run is enrollable
        """
        now = now_in_utc()
        return (
            (self.enrollment_end is None or self.enrollment_end > now)
            and self.enrollment_start is not None
            and self.enrollment_start <= now
            and self.live is True
            and self.start_date is not None
        )

    @property
    def is_fake_course_run(self):
        """
        Checks if a course run is a fake course run
        """
        return self.run_tag.startswith("fake")

    @property
    def courseware_url(self):
        """
        Full URL for this CourseRun as it exists in the courseware.

        This is computed based on the courseware_id (readable_id) using the pattern:
        <edX base URL>/learn/course/<courseware_id>/home

        Returns None if `has_courseware_url` is False. This flag is used for test/placeholder
        runs that should not expose a public courseware URL.

        Configuration Settings:
        - OPENEDX_COURSE_BASE_URL: the base URL for edX course pages

        Returns:
            str or None: Full URL or None if has_courseware_url is False or courseware_id is not set
        """
        # Some course runs (test data, placeholders) should not have a URL
        if not self.has_courseware_url:
            return None

        from courses.utils import get_courseware_url  # noqa: PLC0415

        return get_courseware_url(self.courseware_id)

    @property
    def text_id(self):
        """Gets the courseware_id"""
        return self.courseware_id

    @property
    def course_number(self):
        """
        Returns:
            str: Course number (last part of readable_id, after the final +)
        """
        return get_course_number(self.courseware_id)

    @property
    def readable_id(self):
        """Alias for the courseware_id so this is consistent with Course and Program"""
        return self.courseware_id

    @property
    def is_program(self):
        """Flag to indicate if this is a program"""
        return False

    @property
    def is_run(self):
        """Flag to indicate if this is a run"""
        return True

    def __str__(self):
        title = f"{self.courseware_id} | {self.title}"
        return title if len(title) <= 100 else title[:97] + "..."  # noqa: PLR2004

    def clean(self):
        """
        If expiration_date is not set:
        1. If end_date is provided: set expiration_date to default end_date + 90 days.
        2. If end_date is None, don't do anything.

        Validate that the expiration date is:
        1. Later than end_date if end_date is set
        2. Later than start_date if start_date is set
        """
        if not self.expiration_date:
            return

        if self.start_date and self.expiration_date < self.start_date:
            raise ValidationError("Expiration date must be later than start date.")  # noqa: EM101

        if self.end_date and self.expiration_date < self.end_date:
            raise ValidationError("Expiration date must be later than end date.")  # noqa: EM101

    def save(
        self,
        force_insert=False,  # noqa: FBT002
        force_update=False,  # noqa: FBT002
        using=None,
        update_fields=None,
    ):
        """
        Overriding the save method to inject clean into it.
        """
        self.clean()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )


def limit_to_certificate_pages():
    """
    A callable for the limit_choices_to param in the FKs for certificate pages
    to limit the choices to certificate pages, rather than every page in the
    CMS.
    """
    from cms.models import CertificatePage  # noqa: PLC0415

    available_revisions = CertificatePage.objects.filter(live=True).values_list(
        "id", flat=True
    )
    return {"object_id__in": list(map(str, available_revisions))}


class VerifiableCredential(TimestampedModel):
    """
    Model for storing verifiable credentials for both course runs and programs
    """

    # TODO: Need to determine what this will actually be.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    credential_data = models.JSONField(
        help_text="JSON data representing the verifiable credential"
    )


class BaseCertificate(models.Model):
    """
    Common properties for certificate models
    """

    user = models.ForeignKey(User, null=False, on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_revoked = models.BooleanField(
        default=False,
        help_text="Indicates whether or not the certificate is revoked",
        verbose_name="revoked",
    )
    issue_date = models.DateTimeField(
        null=False, blank=False, db_index=True, default=timezone.now
    )
    verifiable_credential = models.OneToOneField(
        VerifiableCredential, on_delete=models.SET_NULL, blank=True, null=True
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.issue_date:
            self.issue_date = getattr(self, "created_on", None)
        super().save(*args, **kwargs)

    def get_certified_object_id(self):
        """Gets the id of the certificate's program/run"""
        raise NotImplementedError

    def get_courseware_object_readable_id(self):
        """Get the readable id of the certificate's run/program"""
        return NotImplementedError


class CourseRunCertificate(TimestampedModel, BaseCertificate):
    """
    Model for storing course run certificates
    """

    course_run = models.ForeignKey(
        CourseRun,
        null=False,
        on_delete=models.CASCADE,
        related_name="courseruncertificates",
    )
    certificate_page_revision = models.ForeignKey(
        Revision,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        limit_choices_to=limit_to_certificate_pages,
    )

    objects = ActiveCertificates()
    all_objects = models.Manager()  # noqa: DJ012

    class Meta:
        unique_together = ("user", "course_run")

    def get_certified_object_id(self):
        return self.course_run_id

    def get_courseware_object_id(self):
        """Gets the course id instead of the course run id"""
        return self.course_run.course_id

    def get_courseware_object_readable_id(self):
        return self.course_run.courseware_id

    @property
    def link(self) -> str:
        """
        Get the link at which this certificate will be served
        Format: /certificate/<uuid>/
        Example: /certificate/93ebd74e-5f88-4b47-bb09-30a6d575328f/
        """
        return f"/certificate/{self.uuid!s}/"

    @property
    def start_end_dates(self):
        """Returns the start date for courseware object and certificate creation date"""
        return self.course_run.start_date, self.created_on

    def __str__(self):  # noqa: DJ012
        return f'CourseRunCertificate for user={self.user.edx_username}, run={self.course_run.text_id} ({self.uuid})"'

    def clean(self):
        from cms.models import CertificatePage, CoursePage  # noqa: PLC0415

        certpage = CertificatePage.objects.filter(
            pk=int(self.certificate_page_revision.object_id),
        )

        if not certpage.exists():
            raise ValidationError(
                {
                    "certificate_page_revision": f"The selected page {self.certificate_page_revision.content_object} is not a certificate page."
                }
            )

        certpage = certpage.get()

        if (
            not isinstance(certpage.parent, CoursePage)
            or not certpage.parent.course == self.course_run.course
        ):
            raise ValidationError(
                {
                    "certificate_page_revision": f"The selected certificate page {certpage} is not for this course {self.course_run.course}."
                }
            )

    def save(self, *args, **kwargs):  # noqa: DJ012
        if not self.certificate_page_revision:
            certificate_page = (
                self.course_run.course.page.certificate_page
                if self.course_run.course.page
                else None
            )
            if certificate_page:
                self.certificate_page_revision = certificate_page.get_latest_revision()

        super(CourseRunCertificate, self).save(*args, **kwargs)  # noqa: UP008


class ProgramCertificate(TimestampedModel, BaseCertificate):
    """
    Model for storing program certificates
    """

    program = models.ForeignKey(Program, null=False, on_delete=models.CASCADE)
    certificate_page_revision = models.ForeignKey(
        Revision,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        limit_choices_to=limit_to_certificate_pages,
    )

    objects = ActiveCertificates()
    all_objects = models.Manager()  # noqa: DJ012

    class Meta:
        unique_together = ("user", "program")

    def get_certified_object_id(self):
        return self.program_id

    def get_courseware_object_id(self):
        """Gets the program id"""
        return self.program_id

    def get_courseware_object_readable_id(self):
        return self.program.readable_id

    @property
    def link(self) -> str:
        """
        Get the link at which this certificate will be served
        Format: /certificate/program/<uuid>/
        Example: /certificate/program/93ebd74e-5f88-4b47-bb09-30a6d575328f/
        """
        return f"/certificate/program/{self.uuid!s}/"

    @property
    def start_end_dates(self):
        """
        Start date: earliest course run start date
        End date: program certificate creation date
        """
        course_ids = [course[0].id for course in self.program.courses]
        dates = CourseRunCertificate.objects.filter(
            user_id=self.user_id, course_run__course_id__in=course_ids
        ).aggregate(start_date=models.Min("course_run__start_date"))
        return dates["start_date"], self.created_on

    def __str__(self):  # noqa: DJ012
        return f'ProgramCertificate for user={self.user.edx_username}, program={self.program.text_id} ({self.uuid})"'

    def clean(self):
        from cms.models import CertificatePage, ProgramPage  # noqa: PLC0415

        certpage = CertificatePage.objects.filter(
            pk=int(self.certificate_page_revision.object_id),
        )

        if not certpage.exists():
            raise ValidationError(
                {
                    "certificate_page_revision": f"The selected page {self.certificate_page_revision.content_object} is not a certificate page."
                }
            )

        certpage = certpage.get()

        if (
            not isinstance(certpage.parent, ProgramPage)
            or not certpage.parent.program == self.program
        ):
            raise ValidationError(
                {
                    "certificate_page_revision": f"The selected certificate page {certpage} is not for this program {self.program}."
                }
            )

    def save(self, *args, **kwargs):  # pylint: disable=signature-differs  # noqa: DJ012
        if not self.certificate_page_revision:
            certificate_page = (
                self.program.page.certificate_page
                if hasattr(self.program, "page") and self.program.page
                else None
            )
            if certificate_page:
                self.certificate_page_revision = certificate_page.get_latest_revision()

        super().save(*args, **kwargs)


class BlockedCountry(TimestampedModel):
    """Represents a country that is blocked from enrollment for a course"""

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="blocked_countries"
    )
    country = CountryField()

    class Meta:
        verbose_name_plural = "blocked countries"
        unique_together = ("course", "country")

    def __str__(self):
        return f"course='{self.course.title}'; country='{self.country.name}'"


class EnrollmentModel(TimestampedModel, AuditableModel):
    """Abstract base model for enrollments"""

    class Meta:
        abstract = True

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    change_status = models.CharField(  # noqa: DJ001
        choices=ENROLL_CHANGE_STATUS_CHOICES, max_length=20, null=True, blank=True
    )
    active = models.BooleanField(
        default=True,
        help_text="Indicates whether or not this enrollment should be considered active",
    )
    enrollment_mode = models.CharField(  # noqa: DJ001
        default=EDX_DEFAULT_ENROLLMENT_MODE, max_length=20, null=True, blank=True
    )

    objects = ActiveEnrollmentManager()
    all_objects = EnrollmentManager()

    @classmethod
    def get_audit_class(cls):
        raise NotImplementedError

    @classmethod
    def objects_for_audit(cls):
        return cls.all_objects

    def to_dict(self):
        return {
            **serialize_model_object(self),
            "username": self.user.edx_username,
            "full_name": self.user.name,
            "email": self.user.email,
        }

    def deactivate_and_save(self, change_status, no_user=False):  # noqa: FBT002
        """Sets an enrollment to inactive, sets the status, and saves"""
        self.active = False
        self.change_status = change_status
        return self.save_and_log(None if no_user else self.user)

    def reactivate_and_save(self, no_user=False):  # noqa: FBT002
        """Sets an enrollment to be active again and saves"""

        self.active = True
        self.change_status = None
        return self.save_and_log(None if no_user else self.user)

    def update_mode_and_save(self, mode, no_user=False):  # noqa: FBT002
        self.enrollment_mode = mode
        return self.save_and_log(None if no_user else self.user)


class CourseRunEnrollmentCertificatePrefetcher(Prefetcher):
    """Prefetcher for CourseRunEnrollment certificates"""

    @staticmethod
    def mapper(course_run_enrollment):
        """Map each enrollment to (run_id, user_id)"""
        return (course_run_enrollment.run_id, course_run_enrollment.user_id)

    @staticmethod
    def filter(course_run_and_user_ids):
        id_filters = Q()

        # django 5.1 supports this via
        # django.db.models.fields.tuple_lookups.{Tuple,TupleIn}
        for course_run_id, user_id in course_run_and_user_ids:
            id_filters |= Q(course_run_id=course_run_id, user_id=user_id)

        return CourseRunCertificate.objects.filter(id_filters)

    @staticmethod
    def reverse_mapper(certificate):
        return [(certificate.course_run_id, certificate.user_id)]

    @staticmethod
    def decorator(course_run_enrollment, certificates=None):
        course_run_enrollment._certificate = certificates[0] if certificates else None  # noqa: SLF001


class CourseRunEnrollmentGradesPrefetcher(Prefetcher):
    """Prefetcher for CourseRunEnrollment grades"""

    @staticmethod
    def mapper(course_run_enrollment):
        """Map each enrollment to (run_id, user_id)"""
        return (course_run_enrollment.run_id, course_run_enrollment.user_id)

    @staticmethod
    def filter(course_run_and_user_ids):
        id_filters = Q()

        # django 5.1 supports this via
        # django.db.models.fields.tuple_lookups.{Tuple,TupleIn}
        for course_run_id, user_id in course_run_and_user_ids:
            id_filters |= Q(course_run_id=course_run_id, user_id=user_id)

        return CourseRunGrade.objects.filter(id_filters)

    @staticmethod
    def reverse_mapper(grade):
        return [(grade.course_run_id, grade.user_id)]

    @staticmethod
    def decorator(course_run_enrollment, grades=None):
        course_run_enrollment._grades = grades or []  # noqa: SLF001


class CourseRunEnrollmentManager(EnrollmentManager):
    """EnrollmentManager for CourseRunEnrollment"""

    prefetch_definitions = {
        "certificate": CourseRunEnrollmentCertificatePrefetcher,
        "grades": CourseRunEnrollmentGradesPrefetcher,
    }


class ActiveCourseRunEnrollmentManager(ActiveEnrollmentManager):
    """ActiveEnrollmentManager for CourseRunEnrollment"""

    prefetch_definitions = CourseRunEnrollmentManager.prefetch_definitions


class CourseRunEnrollment(EnrollmentModel):
    """
    Link between User and CourseRun indicating a user's enrollment
    """

    run = models.ForeignKey(
        "courses.CourseRun", related_name="enrollments", on_delete=models.CASCADE
    )
    edx_enrolled = models.BooleanField(
        default=False,
        help_text="Indicates whether or not the request succeeded to enroll via the edX API",
    )
    edx_emails_subscription = models.BooleanField(default=True)

    objects = ActiveCourseRunEnrollmentManager()
    all_objects = CourseRunEnrollmentManager()

    class Meta:
        unique_together = ("user", "run")

    @property
    def is_ended(self):
        """Return True, if run associated with enrollment is ended."""
        return self.run.is_past

    @classmethod
    def get_audit_class(cls):
        return CourseRunEnrollmentAudit

    @cached_property
    def certificate(self) -> CourseRunCertificate | None:
        if hasattr(self, "_certificate"):
            return self._certificate
        else:
            return CourseRunCertificate.objects.filter(
                course_run_id=self.run_id, user_id=self.user_id
            ).first()

    @cached_property
    def grades(self) -> list["CourseRunGrade"]:
        if hasattr(self, "_grades"):
            return self._grades
        else:
            return list(
                CourseRunGrade.objects.filter(
                    course_run_id=self.run_id, user_id=self.user_id
                )
            )

    @classmethod
    def get_program_run_enrollments(cls, user, program):
        """
        Fetches the CourseRunEnrollments associated with a given user and program

        Args:
            user (User): A user
            program (Program): A program

        Returns:
            queryset of CourseRunEnrollment: Course run enrollments associated with a user/program
        """
        program_courses = [course[0] for course in program.courses]
        return cls.objects.filter(user=user, run__course__in=program_courses)

    def change_payment_to_run(self, to_run):
        """
        During a deferral process, if user has paid for this run
        we can change the payment to another run
        """
        # Due to circular dependancy importing locally
        from ecommerce.models import OrderStatus  # noqa: PLC0415

        paid_run = PaidCourseRun.objects.filter(
            user=self.user,
            course_run=self.run,
            order__state=OrderStatus.FULFILLED,
        ).first()
        if paid_run:
            paid_run.course_run = to_run
            paid_run.save()

    def to_dict(self):
        return {**super().to_dict(), "text_id": self.run.courseware_id}

    def __str__(self):
        return f"CourseRunEnrollment for {self.user} and {self.run}"


class CourseRunEnrollmentAudit(AuditModel):
    """Audit table for CourseRunEnrollment"""

    enrollment = models.ForeignKey(
        CourseRunEnrollment, null=True, on_delete=models.CASCADE
    )

    @classmethod
    def get_related_field_name(cls):
        return "enrollment"


class ProgramEnrollmentCertificatePrefetcher(Prefetcher):
    """Prefetcher for ProgramEnrollment certificates"""

    @staticmethod
    def mapper(program_enrollment):
        """Map each unrollment to (program_id, user_id)"""
        return (program_enrollment.program_id, program_enrollment.user_id)

    @staticmethod
    def filter(program_and_user_ids):
        id_filters = Q()

        # django 5.1 supports this via
        # django.db.models.fields.tuple_lookups.{Tuple,TupleIn}
        for program_id, user_id in program_and_user_ids:
            id_filters |= Q(program_id=program_id, user_id=user_id)

        return ProgramCertificate.objects.filter(id_filters)

    @staticmethod
    def reverse_mapper(certificate):
        return [(certificate.program_id, certificate.user_id)]

    @staticmethod
    def decorator(program_enrollment, certificates=()):
        program_enrollment._certificate = certificates[0] if certificates else None  # noqa: SLF001


class ProgramEnrollmentManager(EnrollmentManager):
    """EnrollmentManager for ProgramEnrollment"""

    prefetch_definitions = {"certificate": ProgramEnrollmentCertificatePrefetcher}


class ActiveProgramEnrollmentManager(ActiveEnrollmentManager):
    """ActiveEnrollmentManager for ProgramEnrollment"""

    prefetch_definitions = ProgramEnrollmentManager.prefetch_definitions


class ProgramEnrollment(EnrollmentModel):
    """
    Link between User and Program indicating a user's enrollment
    """

    program = models.ForeignKey(
        "courses.Program", on_delete=models.CASCADE, related_name="enrollments"
    )

    objects = ActiveProgramEnrollmentManager()
    all_objects = ProgramEnrollmentManager()

    class Meta:
        unique_together = ("user", "program")

    @property
    def is_ended(self):
        """Return True, if runs associated with enrollment are ended."""
        return all(enrollment.run.is_past for enrollment in self.get_run_enrollments())

    @classmethod
    def get_audit_class(cls):
        return ProgramEnrollmentAudit

    @cached_property
    def certificate(self):
        if hasattr(self, "_certificate"):
            return self._certificate
        else:
            return ProgramCertificate.objects.filter(
                program_id=self.program_id, user_id=self.user_id
            ).first()

    def get_run_enrollments(self):
        """
        Fetches the CourseRunEnrollments associated with this ProgramEnrollment

        Returns:
            queryset of CourseRunEnrollment: Associated course run enrollments
        """
        return CourseRunEnrollment.get_program_run_enrollments(
            user=self.user, program=self.program
        )

    def to_dict(self):
        return {**super().to_dict(), "text_id": self.program.readable_id}

    def __str__(self):
        return f"ProgramEnrollment for {self.user} and {self.program}"


class ProgramEnrollmentAudit(AuditModel):
    """Audit table for ProgramEnrollment"""

    enrollment = models.ForeignKey(
        ProgramEnrollment, null=True, on_delete=models.CASCADE
    )

    @classmethod
    def get_related_field_name(cls):
        return "enrollment"


class CourseRunGrade(TimestampedModel, AuditableModel, ValidateOnSaveMixin):
    """
    Model to store course run final grades
    """

    user = models.ForeignKey(User, null=False, on_delete=models.CASCADE)
    course_run = models.ForeignKey(
        CourseRun, null=False, on_delete=models.CASCADE, related_name="grades"
    )
    grade = models.FloatField(
        null=False, validators=[MinValueValidator(0.0), MaxValueValidator(2.0)]
    )
    letter_grade = models.CharField(max_length=10, blank=True, null=True)  # noqa: DJ001
    passed = models.BooleanField(default=False)
    set_by_admin = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "course_run")

    @classmethod
    def get_audit_class(cls):
        return CourseRunGradeAudit

    def to_dict(self):
        return serialize_model_object(self)

    @property
    def grade_percent(self) -> Decimal:
        """Returns the grade field value as a number out of 100 (or Decimal(0) if the value is None)"""
        return (
            Decimal(self.grade * 100).quantize(exp=Decimal(1), rounding=ROUND_HALF_EVEN)
            if self.grade is not None
            else Decimal(0)
        )

    @property
    def is_certificate_eligible(self):
        """For a user to be eligible for a certificate:
        1. He should have a passing grade (passed=True)
        2. He should have a paid enrollment (e.g. Verified)
        """
        return (
            self.passed
            and CourseRunEnrollment.objects.filter(
                user=self.user,
                run=self.course_run,
                enrollment_mode__in=EDX_ENROLLMENTS_PAID_MODES,
            ).exists()
        )

    def __str__(self):
        return f"CourseRunGrade for run '{self.course_run.courseware_id}', user '{self.user.edx_username}' ({self.grade})"


class CourseRunGradeAudit(AuditModel):
    """CourseRunGrade audit table"""

    course_run_grade = models.ForeignKey(
        CourseRunGrade, null=True, on_delete=models.SET_NULL
    )

    @classmethod
    def get_related_field_name(cls):
        return "course_run_grade"


class PaidCourseRun(TimestampedModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="paid_course_runs"
    )

    course_run = models.ForeignKey(
        CourseRun, on_delete=models.CASCADE, related_name="paid_course_runs"
    )

    order = models.ForeignKey(
        "ecommerce.Order", on_delete=models.CASCADE, related_name="paid_course_runs"
    )

    class Meta:
        unique_together = ("user", "course_run", "order")

    def __str__(self):
        return f"Paid Course Run - {self.course_run.courseware_id} by {self.user.name}"

    @classmethod
    def fulfilled_paid_course_run_exists(cls, user: User, run: CourseRun):
        """
        Checks if user has paid course run
        Returns True if PaidCourseRun exists else False.
        Args:
            products (list): List of products.
        Returns:
            Boolean
        """

        # Due to circular dependancy importing locally
        from ecommerce.models import OrderStatus  # noqa: PLC0415

        # PaidCourseRun should only contain fulfilled orders
        return cls.objects.filter(
            user=user,
            course_run=run,
            order__state=OrderStatus.FULFILLED,
        ).exists()


class PaidProgram(TimestampedModel):
    """Stores a record of programs that the user has paid for."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="paid_programs"
    )

    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="paid_programs"
    )

    order = models.ForeignKey(
        "ecommerce.Order", on_delete=models.CASCADE, related_name="paid_programs"
    )

    class Meta:
        unique_together = ("user", "program", "order")

    def __str__(self):
        return f"Paid Program - {self.program.readable_id} by {self.user.name}"

    @classmethod
    def fulfilled_paid_program_exists(cls, user: User, program: Program):
        """
        Checks if user has paid course run
        Returns True if PaidCourseRun exists else False.
        Args:
            products (list): List of products.
        Returns:
            Boolean
        """

        # Due to circular dependancy importing locally
        from ecommerce.models import OrderStatus  # noqa: PLC0415

        # PaidCourseRun should only contain fulfilled orders
        return cls.objects.filter(
            user=user,
            program=program,
            order__state=OrderStatus.FULFILLED,
        ).exists()


class ProgramRequirementNodeType(models.TextChoices):
    PROGRAM_ROOT = "program_root", "Program Root"
    OPERATOR = "operator", "Operator"
    COURSE = "course", "Course"
    PROGRAM = "program", "Program"


class ProgramRequirement(MP_Node):
    """
    A representation of program requirements.

    There are 3 types of nodes that exist in a requirement tree:

    Root nodes - these represent a program
    Operator nodes - these represent a logical operation over a set of courses
    Course nodes - these represent a reference to a course

    Usage:

    root = ProgramRequirement.add_root(program=program)

    required_courses = root.add_child(operator=ProgramRequirement.Operator.all_of, title="Required Courses")
    required_courses.add_child(course=course1)
    required_courses.add_child(course=course2)

    # at least two must be taken
    elective_courses = root.add_child(
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=2,
        title="Elective Courses"
    )
    elective_courses.add_child(course=course3)
    elective_courses.add_child(course=course4)

    # 3rd elective option is at least one of these courses
    mut_exclusive_courses = elective_courses.add_child(
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=1
    )
    mut_exclusive_courses.add_child(course=course5)
    mut_exclusive_courses.add_child(course=course6)

    """

    # extended alphabet from the default to the recommended one for postgres
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

    # we override to use C collation so that lowercase letters sort after uppercase
    # regardless of the DB's underlying OS collation
    path = models.CharField(max_length=255, unique=True, db_collation="C")

    node_type = models.CharField(  # noqa: DJ001
        choices=ProgramRequirementNodeType,
        max_length=len(max(ProgramRequirementNodeType.values, key=len)),
        null=True,
    )

    class Operator(models.TextChoices):
        ALL_OF = "all_of", "All of"
        MIN_NUMBER_OF = "min_number_of", "Minimum # of"

    operator = models.CharField(  # noqa: DJ001
        choices=Operator,
        max_length=len(max(Operator.values, key=len)),
        null=True,
    )
    operator_value = models.CharField(max_length=100, null=True)  # noqa: DJ001

    program = models.ForeignKey(
        "courses.Program", on_delete=models.CASCADE, related_name="all_requirements"
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="in_programs",
    )
    required_program = models.ForeignKey(
        "courses.Program",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="required_by",
        help_text="Program that is required to be completed",
    )

    title = models.TextField(null=True, blank=True, default="")  # noqa: DJ001
    elective_flag = models.BooleanField(null=True, blank=True, default=False)

    @property
    def is_all_of_operator(self):
        """True if the node is an ALL_OF operator"""
        return self.operator == self.Operator.ALL_OF

    @property
    def is_min_number_of_operator(self):
        """True if the node is a MIN_NUMBER_OF operator"""
        return self.operator == self.Operator.MIN_NUMBER_OF

    @property
    def is_operator(self):
        """True if the node is an operator"""
        return self.node_type == ProgramRequirementNodeType.OPERATOR

    @property
    def is_course(self):
        """True if the node references a course"""
        return self.node_type == ProgramRequirementNodeType.COURSE

    @property
    def is_program(self):
        """True if the node references a program"""
        return self.node_type == ProgramRequirementNodeType.PROGRAM

    @property
    def is_root(self):
        """True if the node is the root"""
        return self.node_type == ProgramRequirementNodeType.PROGRAM_ROOT

    def add_child(self, **kwargs):
        """Children must always have the same program"""
        kwargs["program"] = self.program
        return super().add_child(**kwargs)

    def __str__(self):
        attrs = {
            "id": self.id,
            "program": self.program.readable_id,
            "node_type": self.node_type,
        }

        if self.is_operator:
            attrs["operator"] = self.operator
            attrs["operator_value"] = self.operator_value
        elif self.is_course:
            attrs["course"] = self.course
        elif self.is_program:
            attrs["required_program"] = self.required_program

        return " ".join(f"{key}={value}" for key, value in attrs.items())

    class Meta:
        constraints = (
            # validate the fields based on the node 'type'
            CheckConstraint(
                name="courses_programrequirement_node_check",
                condition=(
                    # root nodes
                    Q(
                        node_type=ProgramRequirementNodeType.PROGRAM_ROOT.value,
                        operator__isnull=True,
                        operator_value__isnull=True,
                        course__isnull=True,
                        required_program__isnull=True,
                        depth=1,
                    )
                    # operator nodes
                    | Q(
                        node_type=ProgramRequirementNodeType.OPERATOR.value,
                        operator__isnull=False,
                        course__isnull=True,
                        required_program__isnull=True,
                        depth__gt=1,
                    )
                    # course nodes
                    | Q(
                        node_type=ProgramRequirementNodeType.COURSE.value,
                        operator__isnull=True,
                        operator_value__isnull=True,
                        course__isnull=False,
                        required_program__isnull=True,
                        depth__gt=1,
                    )
                    # program nodes
                    | Q(
                        node_type=ProgramRequirementNodeType.PROGRAM.value,
                        operator__isnull=True,
                        operator_value__isnull=True,
                        course__isnull=True,
                        required_program__isnull=False,
                        depth__gt=1,
                    )
                ),
            ),
            # only all 1 root node per program
            UniqueConstraint(
                name="courses_programrequirement_root_uniq",
                fields=("program", "depth"),
                condition=Q(depth=1),
            ),
        )
        indexes = [
            models.Index(fields=("program", "course")),
            models.Index(fields=("course", "program")),
            models.Index(fields=("program", "required_program")),
            models.Index(fields=("required_program", "program")),
            models.Index(fields=("program", "node_type", "depth")),
        ]


class PartnerSchool(TimestampedModel):
    """
    Model for partner school to send records to (copied from MicroMasters)
    """

    name = models.CharField(max_length=255)
    email = models.TextField(null=False)

    def __str__(self):
        return self.name


class LearnerProgramRecordShare(TimestampedModel):
    """
    Tracks the sharing status of an individual learner's program record.

    partner_school is null if the record is for the learner's public sharing link.
    """

    share_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    program = models.ForeignKey(
        "courses.Program", on_delete=models.CASCADE, related_name="+"
    )
    partner_school = models.ForeignKey(
        "courses.PartnerSchool",
        on_delete=models.CASCADE,
        related_name="shares",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True, blank=True)

    def __str__(self):
        if self.partner_school:
            return f"Learner Program Record for {self.user.edx_username} shared with partner school {self.partner_school.name} on {self.created_on} - {self.share_uuid}"
        else:
            return f"Learner Program record for {self.user.edx_username} shared with the public on {self.created_on} - {self.share_uuid}"

    class Meta:
        constraints = [
            UniqueConstraint(
                name="record_share_partner_school_unique",
                fields=("program", "user", "partner_school"),
            )
        ]


class ProgramCollectionItem(Orderable):
    """Intermediate model to store programs in a collection with ordering"""

    collection = ParentalKey(
        "ProgramCollection", on_delete=models.CASCADE, related_name="collection_items"
    )
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="collection_memberships"
    )

    panels = [
        FieldPanel("program"),
    ]

    class Meta:
        ordering = ["sort_order"]
        unique_together = ("collection", "program")
        verbose_name = "Program Collection Item"
        verbose_name_plural = "Program Collection Items"

    def __str__(self):
        return (
            f"{self.collection.title} - {self.program.title} (order: {self.sort_order})"
        )


class ProgramCollection(Page, ClusterableModel):
    """Model for a collection of programs with title and description"""

    description = RichTextField(
        blank=True, help_text="Description of the program collection"
    )

    content_panels = [
        *Page.content_panels,
        FieldPanel("description"),
        InlinePanel(
            "collection_items",
            label="Programs",
            help_text="Add and order programs in this collection",
        ),
    ]

    @property
    def programs(self):
        """
        Returns programs in the collection ordered by their order field
        """
        return Program.objects.filter(collection_memberships__collection=self).order_by(
            "collection_memberships__sort_order"
        )

    @property
    def ordered_collection_items(self):
        """
        Returns ProgramCollectionItem objects ordered by their order field
        """
        return self.collection_items.all().order_by("sort_order")

    def add_program(self, program, order=None):
        """
        Add a program to this collection with optional order

        Args:
            program: Program instance to add
            order: Optional order position. If None, adds at the end
        """
        if order is None:
            last_item = self.collection_items.order_by("-sort_order").first()
            order = (last_item.sort_order + 1) if last_item else 0

        collection_item, created = ProgramCollectionItem.objects.get_or_create(
            collection=self, program=program, defaults={"sort_order": order}
        )

        if not created:
            collection_item.sort_order = order
            collection_item.save()

        return collection_item

    def remove_program(self, program):
        """
        Remove a program from this collection

        Args:
            program: Program instance to remove
        """
        ProgramCollectionItem.objects.filter(collection=self, program=program).delete()

    def reorder_programs(self, program_order_list):
        """
        Reorder programs in the collection

        Args:
            program_order_list: List of (program_id, order) tuples
        """
        for program_id, order in program_order_list:
            ProgramCollectionItem.objects.filter(
                collection=self, program_id=program_id
            ).update(sort_order=order)

    class Meta:
        verbose_name = "Program Collection"
        verbose_name_plural = "Program Collections"
