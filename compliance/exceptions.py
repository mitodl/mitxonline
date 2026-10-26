"""Exceptions for the compliance app"""

# Maps CyberSource bill-to field names to the profile field names an API
# consumer should show the user as missing.
BILL_TO_FIELD_TO_PROFILE_FIELD = {
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email",
    "address1": "street_address_1",
    "address2": "street_address_2",
    "locality": "city",
    "country": "country",
    "administrative_area": "state",
    "postal_code": "postal_code",
}


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


class ExportComplianceDataError(ExportComplianceCheckError):
    """
    A user is missing the profile data required to run an export compliance
    check, or has data CyberSource rejected as invalid
    """

    #: Support-facing code for a profile the learner can fix themselves -
    #: unlike ``ExportComplianceError.error_code``, retrying after updating
    #: the profile can succeed.
    error_code = "CS_701"

    def __init__(self, user, missing_fields, msg=None):
        """
        Sets exception properties and adds a default message

        Args:
            user (users.models.User): The user whose profile data can't be used
            missing_fields (list of str): The billTo fields that are empty, or
                that CyberSource rejected
        """
        self.user = user
        self.missing_fields = sorted(set(missing_fields))
        if msg is None:
            msg = (
                f"Unable to verify export compliance for user={user.id}: missing or "
                f"invalid profile information ({', '.join(self.missing_fields)}). "
                "Please update your profile or contact support."
            )
        super().__init__(msg)

    @property
    def profile_fields(self) -> list[str]:
        """The profile field names (as in ``compliance_missing_fields``) to fix."""
        # A name outside the map passes through as-is rather than failing the
        # error response that reports it.
        return sorted(
            {BILL_TO_FIELD_TO_PROFILE_FIELD.get(f, f) for f in self.missing_fields}
        )

    def to_error_detail(self) -> dict:
        """Return a JSON-serializable representation of this error for API responses."""
        return {
            "detail": str(self),
            "missing_fields": self.missing_fields,
        }
