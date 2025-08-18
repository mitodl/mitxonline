"""Course email messages"""

from mitol.mail.messages import TemplatedMessage

from django.conf import settings
from courses.utils import is_uai_course_run


class UAIEmailMixin:
    """Mixin to handle UAI-specific email logic"""

    @classmethod
    def create(cls, **kwargs):
        """Override to handle UAI-specific logic"""
        template_context = kwargs.get("template_context", {})
        enrollment = template_context.get("enrollment")

        if enrollment and is_uai_course_run(enrollment.run):
            template_context["is_uai_enrollment"] = True
            template_context["dashboard_url"] = (
                settings.MIT_LEARN_DASHBOARD_URL
            )
            kwargs["from_email"] = settings.MIT_LEARN_FROM_EMAIL
            kwargs["headers"] = {"Reply-To": settings.MIT_LEARN_REPLY_TO_EMAIL}

        kwargs["template_context"] = template_context
        return super().create(**kwargs)


class CourseRunEnrollmentMessage(UAIEmailMixin, TemplatedMessage):
    """Email message for course enrollment"""

    name = "Course Run Enrollment"
    template_name = "mail/course_run_enrollment"


class CourseRunUnenrollmentMessage(UAIEmailMixin, TemplatedMessage):
    """Email message for course unenrollment"""

    name = "Course Run Unenrollment"
    template_name = "mail/course_run_unenrollment"


class EnrollmentFailureMessage(TemplatedMessage):
    """Email message for enrollment failures"""

    name = "Enrollment Failure"
    template_name = "mail/enrollment_failure"


class PartnerSchoolSharingMessage(TemplatedMessage):
    """Email message for sharing learner records to partner schools"""

    name = "Shared Learner Record"
    template_name = "mail/partner_school_sharing"
