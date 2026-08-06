"""Compliance app models"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from mitol.common.models import TimestampedModel

from users.models import User


def valid_courseware_run_types_list():
    """Return a Q filter limiting content types to CourseRun/Program"""
    return models.Q(app_label="courses", model="courserun") | models.Q(
        app_label="courses", model="program"
    )


class ExportComplianceDecision(models.TextChoices):
    """Decision values for an export compliance check.

    COMPLETED, INVALID_REQUEST, and DECLINED come from CyberSource.
    MANUALLY_APPROVED is set internally when staff approve a learner after
    reviewing a non-accepted result.
    """

    COMPLETED = "COMPLETED"
    INVALID_REQUEST = "INVALID_REQUEST"
    DECLINED = "DECLINED"
    MANUALLY_APPROVED = "MANUALLY_APPROVED"


class ExportComplianceLog(TimestampedModel):
    """
    Encrypted record of a CyberSource export compliance check for a user
    against a specific CourseRun or Program.
    """

    valid_courseware_run_types = valid_courseware_run_types_list()

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="export_compliance_logs"
    )
    courseware_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=valid_courseware_run_types,
    )
    courseware_object_id = models.PositiveIntegerField()
    courseware_object = GenericForeignKey(
        "courseware_content_type", "courseware_object_id"
    )

    decision = models.CharField(max_length=30, blank=True, default="")
    reason_code = models.CharField(max_length=255, blank=True, default="")
    request_id = models.CharField(max_length=255, blank=True, default="")

    encrypted_request = models.TextField()
    encrypted_response = models.TextField()

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_export_compliance_logs",
    )
    approved_on = models.DateTimeField(null=True, blank=True)

    ACCEPTED_DECISIONS = {
        ExportComplianceDecision.COMPLETED,
        ExportComplianceDecision.MANUALLY_APPROVED,
    }

    @property
    def accepted(self) -> bool:
        """Return True if this logged result was an accepted export compliance decision"""
        return self.decision in self.ACCEPTED_DECISIONS

    def check_manual_approval_fields(self):
        """Ensure approved_by/approved_on are set for a manually-approved decision."""
        if self.decision == ExportComplianceDecision.MANUALLY_APPROVED and (
            self.approved_by_id is None or self.approved_on is None
        ):
            message = (
                "approved_by and approved_on are required when decision "
                "is MANUALLY_APPROVED."
            )
            raise ValidationError(message)

    def save(self, *args, **kwargs):
        self.check_manual_approval_fields()
        super().save(*args, **kwargs)

    def clean(self, *args, **kwargs):
        self.check_manual_approval_fields()
        super().clean(*args, **kwargs)

    def __str__(self):
        return (
            f"ExportComplianceLog(user={self.user_id}, "
            f"courseware_object={self.courseware_object}, decision={self.decision!r})"
        )
