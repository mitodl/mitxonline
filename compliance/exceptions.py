"""Exceptions for the compliance app"""


class ExportComplianceCheckError(Exception):
    """Base class for export compliance verification failures"""

    def to_error_detail(self) -> dict:
        """Return a JSON-serializable representation of this error for API responses."""
        return {"detail": str(self)}


class ExportComplianceError(ExportComplianceCheckError):
    """A user failed a CyberSource export compliance check"""

    #: Opaque support-facing code appended to the learner-visible enrollment
    #: error (see ``courses.exceptions.EnrollmentError.from_cause``). Lets a
    #: learner quote something actionable without us disclosing the CyberSource
    #: decision or reason code - those stay in the logs.
    error_code = "CS_700"

    def __init__(self, user, decision, reason_code, msg=None):
        """
        Sets exception properties and adds a default message

        Args:
            user (users.models.User): The user who failed the export compliance check
            decision (str): The decision returned by CyberSource (e.g. "DECLINED")
            reason_code (str or int): The reason code returned by CyberSource
        """
        self.user = user
        self.decision = decision
        self.reason_code = reason_code
        if msg is None:
            msg = (
                "Export compliance check did not accept enrollment for "
                f"user={user.id}: decision={decision!r}, reason_code={reason_code!r}"
            )
        super().__init__(msg)

    def to_error_detail(self) -> dict:
        """Return a JSON-serializable representation of this error for API responses."""
        return {
            "detail": str(self),
            "decision": self.decision,
            "reason_code": self.reason_code,
        }


class ExportComplianceUnavailableError(ExportComplianceCheckError):
    """CyberSource did not answer the export compliance check

    Distinct from ``ExportComplianceError``, which means CyberSource *did*
    answer and the answer was not an accepting one. Here we have no result at
    all - the learner has done nothing wrong and the next attempt may well
    succeed, so the enrollment copy asks them to retry rather than pointing
    them at support.

    Deliberately leaves no ``ExportComplianceLog`` row behind:
    ``get_latest_export_compliance_log`` reuses any non-accepted result for a
    user with no time bound, so recording this would convert a transient
    CyberSource timeout into a permanent block lifted only by staff applying
    ``MANUALLY_APPROVED``.
    """

    #: Support code appended to the learner-visible enrollment error, distinct
    #: from ``ExportComplianceError``'s so support can tell "we couldn't run
    #: the check" apart from "the check came back negative".
    error_code = "CS_503"

    #: Overrides ``EnrollmentError.default_detail`` for this cause. Says only
    #: that enrollment failed and is worth retrying - that a compliance check
    #: exists, let alone that it was what failed, is not the learner's
    #: business (same reasoning as ``EnrollmentError``'s docstring).
    enrollment_detail = (
        "We're unable to complete your enrollment at this time. "
        "Please try again in a few minutes."
    )

    def __init__(self, user, attempts, msg=None):
        """
        Sets exception properties and adds a default message

        Args:
            user (users.models.User): The user whose check could not be run
            attempts (int): How many requests were made before giving up
        """
        self.user = user
        self.attempts = attempts
        if msg is None:
            msg = (
                "Export compliance check unavailable for "
                f"user={user.id} after {attempts} attempt(s)"
            )
        super().__init__(msg)

    def to_error_detail(self) -> dict:
        """Return a JSON-serializable representation of this error for API responses."""
        return {"detail": str(self), "attempts": self.attempts}


class ExportComplianceDataError(ExportComplianceCheckError):
    """A user is missing the profile data required to run an export compliance check"""

    def __init__(self, user, missing_fields, msg=None):
        """
        Sets exception properties and adds a default message

        Args:
            user (users.models.User): The user missing required profile data
            missing_fields (list of str): The billTo fields that could not be populated
        """
        self.user = user
        self.missing_fields = sorted(set(missing_fields))
        if msg is None:
            msg = (
                f"Unable to verify export compliance for user={user.id}: missing "
                f"required profile information ({', '.join(self.missing_fields)}). "
                "Please update your profile or contact support."
            )
        super().__init__(msg)

    def to_error_detail(self) -> dict:
        """Return a JSON-serializable representation of this error for API responses."""
        return {
            "detail": str(self),
            "missing_fields": self.missing_fields,
        }
