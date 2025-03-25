"""User models"""

import uuid
from datetime import timedelta

import pycountry
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Count, DateTimeField, Q
from django.utils.translation import gettext_lazy as _
from mitol.common.models import TimestampedModel
from mitol.common.utils import now_in_utc

from cms.constants import CMS_EDITORS_GROUP_NAME

# Defined in edX Profile model
from users.constants import USERNAME_MAX_LEN

MALE = "m"
FEMALE = "f"
OTHER = "o"
TRANSGENDER = "t"
NONBINARY = "nb"
GENDER_CHOICES = (
    (MALE, "Male"),
    (FEMALE, "Female"),
    (TRANSGENDER, "Transgender"),
    (NONBINARY, "Non-binary/non-conforming"),
    (OTHER, "Other/Prefer Not to Say"),
)

# For edx_gender_choices and edx_state_choices, we don't display this data to
# the learner - it's just for limiting what we send to edX, so these are simple
# lookups. These should be checked occasionally to make sure they reflect what's
# in edX.

# edX gender choices are different than ours
# As of 5-Jun-2023: https://github.com/openedx/edx-platform/blob/c7fc04968f37b252a427e42848c00e30335b15e4/common/djangoapps/student/models/user.py#L456-L461
EDX_GENDER_CHOICES = [
    "m",
    "f",
    "o",
]
EDX_DEFAULT_GENDER_CHOICE = "o"

# edX states are different from what's in ISO3166
# As of 5-Jun-2023: https://github.com/openedx/edx-platform/blob/c7fc04968f37b252a427e42848c00e30335b15e4/common/djangoapps/student/models/user.py#LL491C5-L546C6
EDX_STATE_CHOICES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "AA",
    "AE",
    "AP",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]
EDX_DEFAULT_STATE_CHOICE = None


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

OPENEDX_HIGHEST_EDUCATION_MAPPINGS = (
    (None, None),
    ("Doctorate", "p"),
    ("Master's or professional degree", "m"),
    ("Bachelor's degree", "b"),
    ("Associate degree", "a"),
    ("Secondary/high school", "hs"),
    ("Junior secondary/junior high/middle school", "jhs"),
    ("Elementary/primary school", "el"),
    ("No formal education", "none"),
    ("Other education", "other"),
)


def _post_create_user(user):
    """
    Create records related to the user

    Args:
        user (users.models.User): the user that was just created
    """
    LegalAddress.objects.create(user=user)
    UserProfile.objects.create(user=user)


class UserManager(BaseUserManager):
    """User manager for custom user model"""

    use_in_migrations = True

    @transaction.atomic
    def _create_user(self, username, email, password, **extra_fields):
        """Create and save a user with the given email and password"""
        email = self.normalize_email(email)
        fields = {
            **extra_fields,
            "email": email,
            "global_id": extra_fields.get("global_id"),
        }
        if username is not None:
            fields["username"] = username
        user = self.model(**fields)
        user.set_password(password)
        user.save(using=self._db)
        _post_create_user(user)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        """Create a user"""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password, **extra_fields):
        """Create a superuser"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")  # noqa: EM101
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")  # noqa: EM101

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
    name = models.CharField(blank=True, default="", max_length=255)
    is_staff = models.BooleanField(
        default=False, help_text="The user can access the admin site"
    )
    # When we have deprecated direct login, default the is_active flag to True
    # and remove the related code in authentication/pipeline/user.py.
    is_active = models.BooleanField(
        default=False, help_text="The user account is active"
    )

    # global_id points to the SSO ID for the user (so, usually the Keycloak ID,
    # which is a UUID). We store it as a string in case the SSO source changes.
    # We allow a blank value so we can have out-of-band users - we may want a
    # Django user that's not connected to an SSO user, for instance.
    global_id = models.CharField(
        max_length=36,
        blank=True,
        default="",
        help_text="The SSO ID (usually a Keycloak UUID) for the user.",
    )

    hubspot_sync_datetime = DateTimeField(null=True)

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

    def get_age(self):
        """
        Returns the user's computed age, using the profile year_of_birth field.
        For COPPA reasons this calculates the year assuming Dec 31 @ 11:59:59.
        """

        from users.utils import determine_approx_age

        return determine_approx_age(self.user_profile.year_of_birth)

    def is_coppa_compliant(self):
        return self.get_age() >= 13  # noqa: PLR2004

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
        indexes = [models.Index(fields=("expires_on", "confirmed", "code"))]


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
    state = models.CharField(max_length=255, blank=True, null=True)  # noqa: DJ001

    @property
    def us_state(self):
        """Returns just the state bit, minus the 'US-' part, only for users in the US."""

        if self.country == "US" and self.state is not None:
            state = self.state.split("-")[1]

            if state in EDX_STATE_CHOICES:
                return state
            else:
                return EDX_DEFAULT_STATE_CHOICE

        return None

    @property
    def edx_us_state(self):
        """Validates the us_state against the list from edx."""

        if self.us_state is not None and self.us_state in EDX_STATE_CHOICES:
            return self.us_state
        else:
            return EDX_DEFAULT_STATE_CHOICE

    def __str__(self):
        """Str representation for the legal address"""
        return f"Legal address for {self.user}"


class UserProfile(TimestampedModel):
    """A user's profile"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="user_profile"
    )

    gender = models.CharField(  # noqa: DJ001
        max_length=128, blank=True, null=True, choices=GENDER_CHOICES
    )
    year_of_birth = models.IntegerField(blank=True, null=True)

    addl_field_flag = models.BooleanField(
        default=False,
        blank=True,
        help_text="Flags if we've asked the user for additional information",
    )

    company = models.CharField(max_length=128, blank=True, null=True, default="")  # noqa: DJ001
    job_title = models.CharField(max_length=128, blank=True, null=True, default="")  # noqa: DJ001
    industry = models.CharField(max_length=60, blank=True, null=True, default="")  # noqa: DJ001
    job_function = models.CharField(max_length=60, blank=True, null=True, default="")  # noqa: DJ001
    company_size = models.IntegerField(
        null=True, blank=True, choices=COMPANY_SIZE_CHOICES
    )
    years_experience = models.IntegerField(
        null=True, blank=True, choices=YRS_EXPERIENCE_CHOICES
    )
    leadership_level = models.CharField(  # noqa: DJ001
        max_length=60, null=True, blank=True, default=""
    )
    highest_education = models.CharField(  # noqa: DJ001
        null=True,
        max_length=60,
        blank=True,
        default="",
        choices=HIGHEST_EDUCATION_CHOICES,
    )
    type_is_student = models.BooleanField(
        null=True,
        default=False,
        blank=True,
        help_text="The learner identifies as type Student",
    )
    type_is_professional = models.BooleanField(
        default=False,
        null=True,
        blank=True,
        help_text="The learner identifies as type Professional",
    )
    type_is_educator = models.BooleanField(
        null=True,
        default=False,
        blank=True,
        help_text="The learner identifies as type Educator",
    )
    type_is_other = models.BooleanField(
        default=False,
        null=True,
        blank=True,
        help_text="The learner identifies as type Other (not professional, student, or educator)",
    )

    @property
    def level_of_education(self):
        """Open edX uses codes for this so we need to map our values."""
        return (
            [  # noqa: RUF015
                item[1]
                for item in OPENEDX_HIGHEST_EDUCATION_MAPPINGS
                if item[0] == self.highest_education
            ][0]
            if self.highest_education
            else ""
        )

    @property
    def edx_gender(self):
        """Validate the gender selection against edx values."""
        if self.gender is not None and self.gender in EDX_GENDER_CHOICES:
            return self.gender
        elif self.gender is not None:
            return EDX_DEFAULT_GENDER_CHOICE

        return None

    def __str__(self):
        """Str representation for the profile"""
        return f"UserProfile for {self.user}"


class BlockList(TimestampedModel):
    """A user's blocklist model"""

    hashed_email = models.CharField(max_length=128)
