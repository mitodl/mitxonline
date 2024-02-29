"""
Course models
"""
import logging
import operator as op
import traceback
import uuid
from decimal import ROUND_HALF_EVEN, Decimal
from django.db import transaction

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.utils.functional import cached_property
from django_countries.fields import CountryField
from mitol.common.models import TimestampedModel
from mitol.common.utils.collections import first_matching_item
from mitol.common.utils.datetime import now_in_utc
from mitol.openedx.utils import get_course_number
from treebeard.mp_tree import MP_Node
from wagtail.models import Revision

from courses.constants import (
    ENROLL_CHANGE_STATUS_CHOICES,
    ENROLLABLE_ITEM_ID_SEPARATOR,
    SYNCED_COURSE_RUN_FIELD_MSG,
)
from main.models import AuditableModel, AuditModel, ValidateOnSaveMixin
from main.utils import serialize_model_object
from openedx.constants import EDX_DEFAULT_ENROLLMENT_MODE, EDX_ENROLLMENTS_PAID_MODES
from openedx.utils import edx_redirect_url

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
    def live(self):
        """Applies a filter for Course runs with live=True"""
        return self.filter(live=True)

    def available(self):
        """Applies a filter for Course runs with end_date in future"""
        return self.filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gt=now_in_utc())
        )

    def with_text_id(self, text_id):
        """Applies a filter for the CourseRun's courseware_id"""
        return self.filter(courseware_id=text_id)


class ActiveEnrollmentManager(models.Manager):
    """Query manager for active enrollment model objects"""

    def get_queryset(self):
        """Manager queryset"""
        return super().get_queryset().filter(active=True)


detail_path_char_pattern = r"\w\-+:\."
validate_url_path_field = RegexValidator(
    r"^[{}]+$".format(detail_path_char_pattern),
    "This field is used to produce URL paths. It must contain only characters that match this pattern: [{}]".format(
        detail_path_char_pattern
    ),
)


class Department(TimestampedModel):
    """
    Departments.
    """

    name = models.CharField(max_length=128, unique=True)

    def __str__(self):
        return self.name


class Program(TimestampedModel, ValidateOnSaveMixin):
    """Model for a course program"""

    class Meta:
        ordering = ["id"]

    objects = ProgramQuerySet.as_manager()
    title = models.CharField(max_length=255)
    readable_id = models.CharField(
        max_length=255, unique=True, validators=[validate_url_path_field]
    )
    live = models.BooleanField(default=False, db_index=True)
    program_type = models.CharField(
        max_length=255,
        default="Series",
        blank=True,
        null=True,
    )
    departments = models.ManyToManyField(Department, blank=True)

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

        return the_jam

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

    def add_requirement(self, course):
        """Makes the specified course a required course"""

        self.get_requirements_root().get_children().filter(course=course).delete()

        new_req = self._add_course_node(ProgramRequirement.Operator.ALL_OF).add_child(
            course=course, node_type=ProgramRequirementNodeType.COURSE
        )

        return new_req

    def add_elective(self, course):
        """Makes the specified course an elective course"""
        self.get_requirements_root().get_children().filter(course=course).delete()

        new_req = self._add_course_node(
            ProgramRequirement.Operator.MIN_NUMBER_OF
        ).add_child(course=course, node_type=ProgramRequirementNodeType.COURSE)

        return new_req

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

        course_ids = [
            course_id
            for course_id in ProgramRequirement.objects.filter(
                program=self, node_type=ProgramRequirementNodeType.COURSE
            )
            .all()
            .values_list("course__id", flat=True)
        ]

        return Course.objects.filter(id__in=course_ids)

    @property
    def courses(self):
        """
        Returns the courses associated with this program via the requirements
        tree. This returns a flat list, not a QuerySet.

        Returns:
        - list of tuple (Course, string): courses that are either requirements or electives, plus the requirement type
        """

        heap = []
        main_ops = ProgramRequirement.objects.filter(program=self, depth=2).all()

        for op in main_ops:
            reqs = (
                ProgramRequirement.objects.filter(
                    program__id=self.id,
                    path__startswith=op.path,
                    node_type=ProgramRequirementNodeType.COURSE,
                )
                .select_related("course")
                .all()
            )

            heap.extend(
                [
                    (
                        req.course,
                        "Required Courses"
                        if not op.elective_flag
                        else "Elective Courses",
                    )
                    for req in reqs
                ]
            )

        return heap

    @cached_property
    def required_courses(self):
        """
        Returns just the courses under the "Required Courses" node.
        """
        return [course for (course, type) in self.courses if type == "Required Courses"]

    @cached_property
    def required_title(self):
        """
        Returns the title of the requirements node that holds the required
        courses (e.g. the one that has elective_flag = False).
        """

        return (
            self.requirements_root.get_children()
            .filter(elective_flag=False)
            .get()
            .title
        )

    @cached_property
    def elective_courses(self):
        """
        Returns just the courses under the "Required Courses" node.
        """
        return [course for (course, type) in self.courses if type == "Elective Courses"]

    def __str__(self):
        title = f"{self.readable_id} | {self.title}"
        return title if len(title) <= 100 else title[:97] + "..."

    @cached_property
    def elective_title(self):
        """
        Returns the title of the requirements node that holds the elective
        courses (e.g. the one that has elective_flag = True).
        """

        return (
            self.requirements_root.get_children().filter(elective_flag=True).get().title
        )

    @cached_property
    def minimum_elective_courses_requirement(self):
        """
        Returns the (int) value defined for the minimum number of elective courses required to be completed by the Program

        Returns:
            int: Minimum number of elective courses required to be completed by the Program.
                Returns None, if no value is defined or elective node is absent.
        """
        operator_nodes = self.requirements_root.get_children()
        for operator_node in operator_nodes:
            if operator_node.is_min_number_of_operator:
                # has passed a minimum of the child requirements
                return int(operator_node.operator_value)

        return None


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

    def __str__(self):
        return f"{self.program.readable_id} | {self.program.title}"


class Course(TimestampedModel, ValidateOnSaveMixin):
    """Model for a course"""

    class Meta:
        ordering = ["id"]

    objects = CourseQuerySet.as_manager()
    title = models.CharField(max_length=255)
    readable_id = models.CharField(
        max_length=255, unique=True, validators=[validate_url_path_field]
    )
    live = models.BooleanField(default=False, db_index=True)
    departments = models.ManyToManyField(Department, blank=True)
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

    @property
    def first_unexpired_run(self):
        """
        Gets the first unexpired CourseRun associated with this Course

        Returns:
            CourseRun or None: An unexpired course run

        # NOTE: This is implemented with sorted() and courseruns.all() to allow for prefetch_related
        #   optimization. You can get the desired course_run with a filter, but
        #   that would run a new query even if prefetch_related was used.
        """
        course_runs = self.courseruns.all()
        eligible_course_runs = [
            course_run
            for course_run in course_runs
            if course_run.live and course_run.start_date and course_run.is_unexpired
        ]
        return first_matching_item(
            sorted(eligible_course_runs, key=lambda course_run: course_run.start_date),
            lambda course_run: True,
        )

    @property
    def unexpired_runs(self):
        """
        Gets all the unexpired CourseRuns associated with this Course
        """
        return list(
            filter(
                op.attrgetter("is_unexpired"),
                self.courseruns.filter(live=True).order_by("start_date"),
            )
        )

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

        return [
            program
            for program in Program.objects.filter(
                pk__in=[id for id in programs_containing_course]
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

    def available_runs(self, user):
        """
        Get all enrollable runs for a Course that a user has not already enrolled in.

        Args:
            user (users.models.User): The user to check available runs for.

        Returns:
            list of CourseRun: Unexpired and unenrolled Course runs

        """
        enrolled_runs = user.courserunenrollment_set.filter(
            run__course=self
        ).values_list("run__id", flat=True)
        return [run for run in self.unexpired_runs if run.id not in enrolled_runs]

    def __str__(self):
        title = f"{self.readable_id} | {self.title}"
        return title if len(title) <= 100 else title[:97] + "..."


class CourseRun(TimestampedModel):
    """Model for a single run/instance of a course"""

    objects = CourseRunQuerySet.as_manager()
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="courseruns", db_index=True
    )
    # product = GenericRelation(Product, related_query_name="course_run")
    title = models.CharField(
        max_length=255,
        help_text=f"The title of the course. {SYNCED_COURSE_RUN_FIELD_MSG}",
    )
    courseware_id = models.CharField(max_length=255, unique=True)
    run_tag = models.TextField(
        max_length=100,
        help_text="A string that identifies the set of runs that this run belongs to (example: 'R2')",
    )
    courseware_url_path = models.CharField(max_length=500, blank=True, null=True)
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

    class Meta:
        unique_together = ("course", "run_tag")

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
    def is_not_beyond_enrollment(self):
        """
        Checks if the course is not beyond its enrollment period


        Returns:
            boolean: True if enrollment period has begun but not ended
        """
        now = now_in_utc()
        return (
            (self.end_date is None or self.end_date > now)
            and (self.enrollment_end is None or self.enrollment_end > now)
            and (self.enrollment_start is None or self.enrollment_start <= now)
        )

    @property
    def is_unexpired(self):
        """
        Checks if the course is not expired

        Returns:
            boolean: True if course is not expired
        """
        return not self.is_past and self.is_not_beyond_enrollment

    @property
    def is_in_progress(self) -> bool:
        """
        Returns True if the course run has started and has not yet ended
        """
        now = now_in_utc()
        return (
            self.start_date is not None
            and self.start_date <= now
            and (self.end_date is None or self.end_date > now)
        )

    @property
    def is_upgradable(self):
        """
        Checks if the course can be upgraded
        A null value means that the upgrade window is always open
        """
        return self.upgrade_deadline is None or (self.upgrade_deadline > now_in_utc())

    @property
    def courseware_url(self):
        """
        Full URL for this CourseRun as it exists in the courseware

        Returns:
            str or None: Full URL or None
        """
        return (
            edx_redirect_url(self.courseware_url_path)
            if self.courseware_url_path
            else None
        )

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

    def __str__(self):
        title = f"{self.courseware_id} | {self.title}"
        return title if len(title) <= 100 else title[:97] + "..."

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
            raise ValidationError("Expiration date must be later than start date.")

        if self.end_date and self.expiration_date < self.end_date:
            raise ValidationError("Expiration date must be later than end date.")

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        """
        Overriding the save method to inject clean into it
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
    from cms.models import CertificatePage

    available_revisions = CertificatePage.objects.filter(live=True).values_list(
        "id", flat=True
    )
    return {"object_id__in": list(map(str, available_revisions))}


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

    class Meta:
        abstract = True

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
    all_objects = models.Manager()

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
    def link(self):
        """
        Get the link at which this certificate will be served
        Format: /certificate/<uuid>/
        Example: /certificate/93ebd74e-5f88-4b47-bb09-30a6d575328f/
        """
        return "/certificate/{}/".format(str(self.uuid))

    @property
    def start_end_dates(self):
        """Returns the start date for courseware object and certificate creation date"""
        return self.course_run.start_date, self.created_on

    def __str__(self):
        return (
            'CourseRunCertificate for user={user}, run={course_run} ({uuid})"'.format(
                user=self.user.username,
                course_run=self.course_run.text_id,
                uuid=self.uuid,
            )
        )

    def clean(self):
        from cms.models import CertificatePage, CoursePage

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

    def save(self, *args, **kwargs):
        if not self.certificate_page_revision:
            certificate_page = (
                self.course_run.course.page.certificate_page
                if self.course_run.course.page
                else None
            )
            if certificate_page:
                self.certificate_page_revision = certificate_page.get_latest_revision()

        super(CourseRunCertificate, self).save(*args, **kwargs)


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
    all_objects = models.Manager()

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
    def link(self):
        """
        Get the link at which this certificate will be served
        Format: /certificate/program/<uuid>/
        Example: /certificate/program/93ebd74e-5f88-4b47-bb09-30a6d575328f/
        """
        return "/certificate/program/{}/".format(str(self.uuid))

    @property
    def start_end_dates(self):
        """
        Start date: earliest course run start date
        End date: latest course run end date
        """
        course_ids = [course[0].id for course in self.program.courses]
        dates = CourseRunCertificate.objects.filter(
            user_id=self.user_id, course_run__course_id__in=course_ids
        ).aggregate(
            start_date=models.Min("course_run__start_date"),
            end_date=models.Max("course_run__end_date"),
        )
        return dates["start_date"], dates["end_date"]

    def __str__(self):
        return 'ProgramCertificate for user={user}, program={program} ({uuid})"'.format(
            user=self.user.username, program=self.program.text_id, uuid=self.uuid
        )

    def clean(self):
        from cms.models import CertificatePage, ProgramPage

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

    def save(self, *args, **kwargs):  # pylint: disable=signature-differs
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
    change_status = models.CharField(
        choices=ENROLL_CHANGE_STATUS_CHOICES, max_length=20, null=True, blank=True
    )
    active = models.BooleanField(
        default=True,
        help_text="Indicates whether or not this enrollment should be considered active",
    )
    enrollment_mode = models.CharField(
        default=EDX_DEFAULT_ENROLLMENT_MODE, max_length=20, null=True, blank=True
    )

    objects = ActiveEnrollmentManager()
    all_objects = models.Manager()

    @classmethod
    def get_audit_class(cls):
        raise NotImplementedError

    @classmethod
    def objects_for_audit(cls):
        return cls.all_objects

    def to_dict(self):
        return {
            **serialize_model_object(self),
            "username": self.user.username,
            "full_name": self.user.name,
            "email": self.user.email,
        }

    def deactivate_and_save(self, change_status, no_user=False):
        """Sets an enrollment to inactive, sets the status, and saves"""
        self.active = False
        self.change_status = change_status
        return self.save_and_log(None if no_user else self.user)

    def reactivate_and_save(self, no_user=False):
        """Sets an enrollment to be active again and saves"""

        self.active = True
        self.change_status = None
        return self.save_and_log(None if no_user else self.user)

    def update_mode_and_save(self, mode, no_user=False):
        self.enrollment_mode = mode
        return self.save_and_log(None if no_user else self.user)

    @transaction.atomic
    def save_and_log(self, acting_user, *args, **kwargs):
        """
        Saves the object and creates an audit object.

        Args:
            acting_user (User):
                The user who made the change to the model. May be None if inapplicable.
        """
        before_obj = self.objects_for_audit().filter(id=self.id).first()
        self.save(*args, **kwargs)
        self.refresh_from_db()
        before_dict = None
        if before_obj is not None:
            before_dict = before_obj.to_dict()

        call_stack = "".join(traceback.format_stack()[-6:-2])

        audit_kwargs = dict(
            acting_user=acting_user,
            modified_by=call_stack,
            data_before=before_dict,
            data_after=self.to_dict(),
        )
        audit_class = self.get_audit_class()
        audit_kwargs[audit_class.get_related_field_name()] = self
        audit_class.objects.create(**audit_kwargs)


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

    class Meta:
        unique_together = ("user", "run")

    @property
    def is_ended(self):
        """Return True, if run associated with enrollment is ended."""
        return self.run.is_past

    @classmethod
    def get_audit_class(cls):
        return CourseRunEnrollmentAudit

    @property
    def highest_grade(self):
        """Returns the highest grade achieved for the course run."""
        return (
            self.grades.filter(course_run=self, user=self.user)
            .order_by("-grade")
            .first()
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

    def deactivate_and_save(self, change_status, no_user=False):
        """
        For course run enrollments, we need to clear any PaidCourseRun records
        for this enrollment (if any) so they can re-enroll later.
        """
        from courses.tasks import clear_unenrolled_paid_course_run

        clear_unenrolled_paid_course_run.delay(self.id)

        return super().deactivate_and_save(change_status, no_user)

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


class ProgramEnrollment(EnrollmentModel):
    """
    Link between User and Program indicating a user's enrollment
    """

    program = models.ForeignKey(
        "courses.Program", on_delete=models.CASCADE, related_name="enrollments"
    )

    class Meta:
        unique_together = ("user", "program")

    @property
    def is_ended(self):
        """Return True, if runs associated with enrollment are ended."""
        return all(enrollment.run.is_past for enrollment in self.get_run_enrollments())

    @classmethod
    def get_audit_class(cls):
        return ProgramEnrollmentAudit

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
    course_run = models.ForeignKey(CourseRun, null=False, on_delete=models.CASCADE)
    grade = models.FloatField(
        null=False, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    letter_grade = models.CharField(max_length=6, blank=True, null=True)
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
    def grade_percent(self):
        """Returns the grade field value as a number out of 100 (or None if the value is None)"""
        return (
            Decimal(self.grade * 100).quantize(exp=Decimal(1), rounding=ROUND_HALF_EVEN)
            if self.grade is not None
            else None
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
        return "CourseRunGrade for run '{course_id}', user '{user}' ({grade})".format(
            course_id=self.course_run.courseware_id,
            user=self.user.username,
            grade=self.grade,
        )


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
        from ecommerce.models import Order

        # PaidCourseRun should only contain fulfilled orders
        return cls.objects.filter(
            user=user,
            course_run=run,
            order__state=Order.STATE.FULFILLED,
        ).exists()


class ProgramRequirementNodeType(models.TextChoices):
    PROGRAM_ROOT = "program_root", "Program Root"
    OPERATOR = "operator", "Operator"
    COURSE = "course", "Course"


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

    node_type = models.CharField(
        choices=ProgramRequirementNodeType.choices,
        max_length=len(max(ProgramRequirementNodeType.values, key=len)),
        null=True,
    )

    class Operator(models.TextChoices):
        ALL_OF = "all_of", "All of"
        MIN_NUMBER_OF = "min_number_of", "Minimum # of"

    operator = models.CharField(
        choices=Operator.choices,
        max_length=len(max(Operator.values, key=len)),
        null=True,
    )
    operator_value = models.CharField(max_length=100, null=True)

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

    title = models.TextField(null=True, blank=True, default="")
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

        return " ".join(f"{key}={value}" for key, value in attrs.items())

    class Meta:
        constraints = (
            # validate the fields based on the node 'type'
            CheckConstraint(
                name="courses_programrequirement_node_check",
                check=(
                    # root nodes
                    Q(
                        node_type=ProgramRequirementNodeType.PROGRAM_ROOT.value,
                        operator__isnull=True,
                        operator_value__isnull=True,
                        course__isnull=True,
                        depth=1,
                    )
                    # operator nodes
                    | Q(
                        node_type=ProgramRequirementNodeType.OPERATOR.value,
                        operator__isnull=False,
                        course__isnull=True,
                        depth__gt=1,
                    )
                    # course nodes
                    | Q(
                        node_type=ProgramRequirementNodeType.COURSE.value,
                        operator__isnull=True,
                        operator_value__isnull=True,
                        course__isnull=False,
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
        index_together = (
            ("program", "course"),
            ("course", "program"),
        )


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
            return f"Learner Program Record for {self.user.username} shared with partner school {self.partner_school.name} on {self.created_on} - {self.share_uuid}"
        else:
            return f"Learner Program record for {self.user.username} shared with the public on {self.created_on} - {self.share_uuid}"

    class Meta:
        constraints = [
            UniqueConstraint(
                name="record_share_partner_school_unique",
                fields=("program", "user", "partner_school"),
            )
        ]
