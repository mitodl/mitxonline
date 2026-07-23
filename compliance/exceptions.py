"""Exceptions for the compliance app"""


class ExportComplianceCheckError(Exception):
    """Base class for export compliance verification failures"""

    def to_error_detail(self) -> dict:
        """Return a JSON-serializable representation of this error for API responses."""
        return {"detail": str(self)}


class ExportComplianceError(ExportComplianceCheckError):
    """A user failed a CyberSource export compliance check"""

    def __init__(self, user, decision, reason_code, msg=None):
        """
        Sets exception properties and adds a default message

        Args:
            user (users.models.User): The user who failed the export compliance check
            decision (str): The decision returned by CyberSource (e.g. "REJECT")
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
