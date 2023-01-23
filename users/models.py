"""User models"""
import uuid
from datetime import timedelta

import pycountry
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _
from mitol.common.models import TimestampedModel
from mitol.common.utils import now_in_utc

# Defined in edX Profile model
from users.constants import USERNAME_MAX_LEN
from cms.constants import CMS_EDITORS_GROUP_NAME

MALE = "m"
FEMALE = "f"
OTHER = "o"
GENDER_CHOICES = (
    (MALE, "Male"),
    (FEMALE, "Female"),
    (OTHER, "Other/Prefer Not to Say"),
)

COMPANY_SIZE_CHOICES = (
    (None, "----"),
    (1, "Small/Start-up (1+ employees)"),
    (9, "Small/Home office (1-9 employees)"),
    (99, "Small (10-99 employees)"),
    (999, "Small to medium-sized (100-999 employees)"),
    (9999, "Medium-sized (1000-9999 employees)"),
    (10000, "Large Enterprise (10,000+ employees)"),
    (0, "Other (N/A or Don't know)"),
)

YRS_EXPERIENCE_CHOICES = (
    (None, "----"),
    (2, "Less than 2 years"),
    (5, "2-5 years"),
    (10, "6 - 10 years"),
    (15, "11 - 15 years"),
    (20, "16 - 20 years"),
    (21, "More than 20 years"),
    (0, "Prefer not to say"),
)

HIGHEST_EDUCATION_CHOICES = (
    (None, "----"),
    ("Doctorate", "Doctorate"),
    ("Master's or professional degree", "Master's or professional degree"),
    ("Bachelor's degree", "Bachelor's degree"),
    ("Associate degree", "Associate degree"),
    ("Secondary/high school", "Secondary/high school"),
    (
        "Junior secondary/junior high/middle school",
        "Junior secondary/junior high/middle school",
    ),
    ("Elementary/primary school", "Elementary/primary school"),
    ("No formal education", "No formal education"),
    ("Other education", "Other education"),
)


def _post_create_user(user):
    """
    Create records related to the user

    Args:
        user (users.models.User): the user that was just created
    """
    LegalAddress.objects.create(user=user)
    Profile.objects.create(user=user)


class UserManager(BaseUserManager):
    """User manager for custom user model"""

    use_in_migrations = True

    @transaction.atomic
    def _create_user(self, username, email, password, keycloak_uuid, **extra_fields):
        """Create and save a user with the given email and password"""
        email = self.normalize_email(email)
        fields = {**extra_fields, "email": email}
        if username is not None:
            fields["username"] = username
        user = self.model(**fields)
        user.set_password(password)
        user.save(using=self._db)
        _post_create_user(user)
        return user

    def create_user(self, username, email=None, password=None, keycloak_uuid=None, **extra_fields):
        """Create a user"""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, keycloak_uuid, **extra_fields)

    def create_superuser(self, username, email, password, **extra_fields):
        """Create a superuser"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(username, email, password, **extra_fields)


class FaultyOpenEdxUserManager(BaseUserManager):
    """User manager that defines a queryset of Users that are incorrectly configured in the openedx"""

    def get_queryset(self):  # pylint: disable=missing-docstring
        return (
            super()
            .get_queryset()
            .select_related("openedx_api_auth")
            .prefetch_related("openedx_users")
            .annotate(
                openedx_user_count=Count("openedx_users"),
                openedx_api_auth_count=Count("openedx_api_auth"),
            )
            .filter(
                (Q(openedx_user_count=0) | Q(openedx_api_auth_count=0)),
                is_active=True,
            )
        )


class User(AbstractBaseUser, TimestampedModel, PermissionsMixin):
    """Primary user class"""

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "name"]

    # NOTE: Username max length was set to 50 before we lowered it. We're hardcoding this
    # value here now until we are ready to migrate the max length at the database level.
    username = models.CharField(unique=True, max_length=USERNAME_MAX_LEN)
    email = models.EmailField(blank=False, unique=True)
    name = models.TextField(blank=True, default="")
    is_staff = models.BooleanField(
        default=False, help_text="The user can access the admin site"
    )
    is_active = models.BooleanField(
        default=False, help_text="The user account is active"
    )
    keycloak_uuid = models.UUIDField(unique=True, blank=True, null=True)

    objects = UserManager()
    faulty_openedx_users = FaultyOpenEdxUserManager()

    def get_full_name(self):
        """Returns the user's fullname"""
        return self.name

    @property
    def is_editor(self) -> bool:
        """Returns True if the user has editor permissions for the CMS"""
        return (
            self.is_superuser
            or self.is_staff
            or self.groups.filter(name=CMS_EDITORS_GROUP_NAME).exists()
        )

    def __str__(self):
        """Str representation for the user"""
        return f"User username={self.username} email={self.email}"


def generate_change_email_code():
    """Generates a new change email code"""
    return uuid.uuid4().hex


def generate_change_email_expires():
    """Generates the expiry datetime for a change email request"""
    return now_in_utc() + timedelta(minutes=settings.AUTH_CHANGE_EMAIL_TTL_IN_MINUTES)


class ChangeEmailRequest(TimestampedModel):
    """Model for tracking an attempt to change the user's email"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="change_email_attempts"
    )
    new_email = models.EmailField(blank=False)

    code = models.CharField(
        unique=True, blank=False, default=generate_change_email_code, max_length=32
    )
    confirmed = models.BooleanField(default=False)
    expires_on = models.DateTimeField(default=generate_change_email_expires)

    class Meta:
        index_together = ("expires_on", "confirmed", "code")


def validate_iso_3166_1_code(value):
    """
    Verify the value is a known subdivision

    Args:
        value (str): the code value

    Raises:
        ValidationError: raised if not a valid code
    """
    if pycountry.countries.get(alpha_2=value) is None:
        raise ValidationError(
            _("%(value)s is not a valid ISO 3166-1 country code"),
            params={"value": value},
        )


def validate_iso_3166_2_code(value):
    """
    Verify the value is a known subdivision

    Args:
        value (str): the code value

    Raises:
        ValidationError: raised if not a valid code
    """
    if pycountry.subdivisions.get(code=value) is None:
        raise ValidationError(
            _("%(value)s is not a valid ISO 3166-2 subdivision code"),
            params={"value": value},
        )


class LegalAddress(TimestampedModel):
    """A user's legal address, used for SDN compliance"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="legal_address"
    )

    first_name = models.CharField(max_length=60, blank=True)
    last_name = models.CharField(max_length=60, blank=True)
    country = models.CharField(
        max_length=2, blank=True, validators=[validate_iso_3166_1_code]
    )  # ISO-3166-1

    def __str__(self):
        """Str representation for the legal address"""
        return f"Legal address for {self.user}"


class Profile(TimestampedModel):
    """A user's profile"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    def __str__(self):
        """Str representation for the profile"""
        return f"Profile for {self.user}"


class BlockList(TimestampedModel):
    """A user's blocklist model"""

    hashed_email = models.CharField(max_length=128)
