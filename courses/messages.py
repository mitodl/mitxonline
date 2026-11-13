"""Course email messages"""

from django.conf import settings

from mail.messages import SiteTemplatedMessage


class LearnDashboardMixin:
    """Link (un)enrollment emails to the MIT Learn dashboard"""

    @classmethod
    def create(cls, **kwargs):
        """Add the MIT Learn dashboard URL to the template context"""
        kwargs["template_context"] = {
            **kwargs.get("template_context", {}),
            "dashboard_url": settings.MIT_LEARN_DASHBOARD_URL,
        }
        return super().create(**kwargs)


class CourseRunEnrollmentMessage(LearnDashboardMixin, SiteTemplatedMessage):
    """Email message for course enrollment"""

    name = "Course Run Enrollment"
    template_name = "mail/course_run_enrollment"


class CourseRunUnenrollmentMessage(LearnDashboardMixin, SiteTemplatedMessage):
    """Email message for course unenrollment"""

    name = "Course Run Unenrollment"
    template_name = "mail/course_run_unenrollment"


class EnrollmentFailureMessage(SiteTemplatedMessage):
    """Email message for enrollment failures"""

    name = "Enrollment Failure"
    template_name = "mail/enrollment_failure"


class PartnerSchoolSharingMessage(SiteTemplatedMessage):
    """Email message for sharing learner records to partner schools"""

    name = "Shared Learner Record"
    template_name = "mail/partner_school_sharing"
