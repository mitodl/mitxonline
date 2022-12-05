"""Course email messages"""
from mitol.mail.messages import TemplatedMessage


class CourseRunEnrollmentMessage(TemplatedMessage):
    """Email message for course enrollment"""

    name = "Course Run Enrollment"
    template_name = "mail/course_run_enrollment"


class CourseRunUnenrollmentMessage(TemplatedMessage):
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
