"""Courseware models"""

from django.conf import settings
from django.db import models
from mitol.common.models import TimestampedModel
from mitol.common.utils import now_in_utc

from openedx.constants import (
    COURSE_RUN_CLONE_STATUS_CHOICES,
    COURSE_RUN_CLONE_STATUS_CLONED,
    COURSE_RUN_CLONE_STATUS_CLONING,
    COURSE_RUN_CLONE_STATUS_FAILED,
    COURSE_RUN_CLONE_STATUS_PENDING,
    OPENEDX_PLATFORM_CHOICES,
    OPENEDX_USERNAME_MAX_LEN,
    PLATFORM_EDX,
)


class OpenEdxUser(TimestampedModel):
    """Model representing a User in a openedx platform"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="openedx_users",
    )
    platform = models.CharField(
        max_length=20, choices=OPENEDX_PLATFORM_CHOICES, default=PLATFORM_EDX
    )
    edx_username = models.CharField(  # noqa: DJ001
        null=True, unique=True, max_length=OPENEDX_USERNAME_MAX_LEN
    )
    desired_edx_username = models.CharField(  # noqa: DJ001
        null=True, max_length=OPENEDX_USERNAME_MAX_LEN
    )
    has_been_synced = models.BooleanField(
        default=False,
        help_text="Indicates whether a corresponding user has been created on the openedx platform",
    )

    has_sync_error = models.BooleanField(
        default=False,
        help_text="Indicates whether we hit an error or not trying to sync the user",
    )

    sync_error_data = models.JSONField(
        null=True, default=None, help_text="The JSON sync error from openedx"
    )

    def __str__(self):
        return f"OpenEdxUser for {self.user} in {self.platform}"

    class Meta:
        unique_together = ("user", "platform")
        indexes = [
            models.Index(
                fields=["has_been_synced", "has_sync_error"], name="sync_state_idx"
            )
        ]


class CourseRunClone(TimestampedModel):
    """
    Progress of cloning a source course run into edX for a new course run.

    Written by the clone_courserun task, whichever path queued it. Without it,
    a clone that exhausts its retries leaves a local run and product with no
    course in edX, and nothing says so.
    """

    course_run = models.OneToOneField(
        "courses.CourseRun",
        on_delete=models.CASCADE,
        related_name="edx_clone",
    )
    source_courseware_id = models.CharField(max_length=255)
    status = models.CharField(
        max_length=16,
        choices=COURSE_RUN_CLONE_STATUS_CHOICES,
        default=COURSE_RUN_CLONE_STATUS_PENDING,
    )
    attempts = models.PositiveIntegerField(default=0)
    clone_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Stamped just before edX is asked to clone. A retry that finds the "
            "target already in edX treats it as ours only when this is set."
        ),
    )
    error = models.TextField(blank=True, default="")

    def start_attempt(self):
        """Record that a clone attempt is starting."""

        self.status = COURSE_RUN_CLONE_STATUS_CLONING
        self.attempts += 1
        self.save(update_fields=["status", "attempts", "updated_on"])

    def mark_requested(self):
        """Record that edX is about to be asked to clone."""

        self.clone_requested_at = now_in_utc()
        self.save(update_fields=["clone_requested_at", "updated_on"])

    def mark_cloned(self):
        """Record that the clone finished."""

        self.status = COURSE_RUN_CLONE_STATUS_CLONED
        self.error = ""
        self.save(update_fields=["status", "error", "updated_on"])

    def mark_error(self, exc, *, final):
        """
        Record a failed attempt.

        Args:
        - exc (Exception): what the attempt raised
        - final (bool): whether no further attempt is coming
        """

        self.error = f"{type(exc).__name__}: {exc}"
        update_fields = ["error", "updated_on"]
        if final:
            self.status = COURSE_RUN_CLONE_STATUS_FAILED
            update_fields.append("status")
        self.save(update_fields=update_fields)

    def __str__(self):
        return f"CourseRunClone for {self.course_run_id} ({self.status})"


class OpenEdxApiAuth(TimestampedModel):
    """Model that stores OAuth2 tokens for authenticating Open edX API calls"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="openedx_api_auth",
    )

    refresh_token = models.CharField(max_length=128)
    access_token = models.CharField(null=True, max_length=128)  # noqa: DJ001
    access_token_expires_on = models.DateTimeField(null=True)

    def __str__(self):
        return f"OpenEdxApiAuth for {self.user}"

    class Meta:
        indexes = [models.Index(fields=("user", "access_token_expires_on"))]
