"""Course email messages"""

from mail.messages import SiteTemplatedMessage


class CourseRunEnrollmentMessage(SiteTemplatedMessage):
    """Email message for course enrollment"""

    name = "Course Run Enrollment"
    template_name = "mail/course_run_enrollment"


class CourseRunUnenrollmentMessage(SiteTemplatedMessage):
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
