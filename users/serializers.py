"""User serializers"""

import logging
import re

import pycountry
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from requests import HTTPError
from requests.exceptions import ConnectionError as RequestsConnectionError
from rest_framework import serializers
from social_django.models import UserSocialAuth

from b2b.serializers.v0 import ContractPageSerializer
from hubspot_sync.task_helpers import sync_hubspot_user

# from ecommerce.api import fetch_and_serialize_unused_coupons  # noqa: ERA001
from mail import verification_api
from main.constants import USER_REGISTRATION_FAILED_MSG
from openedx.api import validate_username_email_with_edx
from openedx.constants import OPENEDX_USERNAME_MAX_LEN
from openedx.exceptions import EdxApiRegistrationValidationException
from openedx.models import OpenEdxUser
from openedx.tasks import change_edx_user_email_async
from users.models import (
    ChangeEmailRequest,
    LegalAddress,
    User,
    UserOrganization,
    UserProfile,
)

log = logging.getLogger()

US_POSTAL_RE = re.compile(r"[0-9]{5}(-[0-9]{4}){0,1}")
CA_POSTAL_RE = re.compile(r"[A-Z]\d[A-Z] \d[A-Z]\d$", flags=re.I)
USER_GIVEN_NAME_RE = re.compile(
    r"""
    ^                               # Start of string
    (?![~!@&)(+:'.?/,`-]+)          # String should not start from character(s) in this set - They can exist in elsewhere
    ([^/^$#*=\[\]`%_;<>{}\"|]+)     # String should not contain characters(s) from this set - All invalid characters
    $                               # End of string
    """,
    flags=re.I | re.VERBOSE | re.MULTILINE,
)
USERNAME_RE_PARTIAL = r"[\w ._+-]+"
USERNAME_RE = re.compile(rf"(?P<username>{USERNAME_RE_PARTIAL})")
USERNAME_ERROR_MSG = "Username can only contain letters, numbers, spaces, and the following characters: _+-"
USERNAME_ALREADY_EXISTS_MSG = (
    "A user already exists with this username. Please try a different one."
)
EMAIL_CONFLICT_MSG = (
    "This email is associated with an existing account. Please try a different one."
)

OPENEDX_ACCOUNT_CREATION_VALIDATION_MSGS_MAP = {
    "It looks like this username is already taken": USERNAME_ALREADY_EXISTS_MSG,
    "This email is already associated with an existing account": EMAIL_CONFLICT_MSG,
}

EMAIL_ERROR_MSG = "Email address already exists in the system."


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for profile"""

    def validate_year_of_birth(self, value):
        """Validates the year of birth field"""
        from users.utils import determine_approx_age

        if not (value and determine_approx_age(value) >= 13):  # noqa: PLR2004
            raise serializers.ValidationError("Year of Birth provided is under 13")  # noqa: EM101

        return value

    class Meta:
        model = UserProfile
        fields = (
            "gender",
            "year_of_birth",
            "addl_field_flag",
            "company",
            "job_title",
            "industry",
            "job_function",
            "company_size",
            "years_experience",
            "leadership_level",
            "highest_education",
            "type_is_student",
            "type_is_professional",
            "type_is_educator",
            "type_is_other",
        )


class LegalAddressSerializer(serializers.ModelSerializer):
    """Serializer for legal address"""

    # NOTE: the model defines these as allowing empty values for backwards compatibility
    #       so we override them here to require them for new writes
    first_name = serializers.CharField(max_length=60, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=60, required=False, allow_blank=True)
    country = serializers.CharField(max_length=2)
    state = serializers.CharField(
        max_length=10, required=False, allow_blank=True, allow_null=True
    )

    def validate_first_name(self, value):
        """Validates the first name of the user"""
        if value and not USER_GIVEN_NAME_RE.match(value):
            raise serializers.ValidationError("First name is not valid")  # noqa: EM101
        return value

    def validate_last_name(self, value):
        """Validates the last name of the user"""
        if value and not USER_GIVEN_NAME_RE.match(value):
            raise serializers.ValidationError("Last name is not valid")  # noqa: EM101
        return value

    def validate(self, data):
        """Validate the legal address data"""
        errors = {}

        # For POST operations (not partial updates), require first_name and last_name
        request = self.context.get("request", None)
        if request and request.method == "POST":
            if "first_name" not in data or data.get("first_name") is None:
                errors["first_name"] = "This field is required."
            if "last_name" not in data or data.get("last_name") is None:
                errors["last_name"] = "This field is required."

        if errors:
            raise serializers.ValidationError(errors)

        # The CountriesStatesSerializer below only provides state options for
        # US and Canada - pycountry has them for everything but we therefore
        # only test for these two.
        if "country" not in data or data["country"] not in ["US", "CA"]:
            return data
        elif (
            "state" in data
            and data["state"] is not None
            and (
                data["country"] in ["US", "CA"]
                and not pycountry.subdivisions.get(code=data["state"])
            )
        ):
            raise serializers.ValidationError({"state": "Invalid state specified"})

        return data

    class Meta:
        model = LegalAddress
        fields = (
            "first_name",
            "last_name",
            "country",
            "state",
        )


class ExtendedLegalAddressSerializer(LegalAddressSerializer):
    """Serializer class that includes email address as part of the legal address"""

    email = serializers.SerializerMethodField()

    @extend_schema_field(str)
    def get_email(self, instance):
        """Get email from the linked user object"""
        return instance.user.email

    class Meta:
        model = LegalAddress
        fields = LegalAddressSerializer.Meta.fields + ("email",)  # noqa: RUF005


class PublicUserSerializer(serializers.ModelSerializer):
    """Serializer for public user data"""

    username = serializers.CharField(
        source="edx_username",
        required=False,
        allow_null=True,
        max_length=OPENEDX_USERNAME_MAX_LEN,
    )

    class Meta:
        model = User
        fields = ("id", "username", "name", "created_on", "updated_on")


class StaffDashboardUserSerializer(serializers.ModelSerializer):
    """Serializer for data we care about in the staff dashboard"""

    legal_address = LegalAddressSerializer(allow_null=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "name",
            "email",
            "legal_address",
            "is_staff",
            "is_superuser",
        )


class UserOrganizationSerializer(serializers.ModelSerializer):
    """
    Serializer for user organization data.

    Return the user's organizations in a manner that makes them look like
    OrganizationPage objects. (Previously, the user organizations were a queryset
    of OrganizationPages that related to the user, but now we have a through
    table.)
    """

    contracts = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    slug = serializers.SerializerMethodField()

    @extend_schema_field(ContractPageSerializer(many=True))
    def get_contracts(self, instance):
        """Get the contracts for the organization for the user"""
        contracts = (
            self.context["user"]
            .b2b_contracts.filter(
                organization=instance.organization,
            )
            .all()
        )
        return ContractPageSerializer(contracts, many=True).data

    @extend_schema_field(int)
    def get_id(self, instance):
        """Get id"""
        return instance.organization.id

    @extend_schema_field(str)
    def get_name(self, instance):
        """Get name"""
        return instance.organization.name

    @extend_schema_field(str)
    def get_description(self, instance):
        """Get description"""
        return instance.organization.description

    def get_logo(self, instance):
        """Get logo"""
        return instance.organization.logo if instance.organization.logo else None

    @extend_schema_field(str)
    def get_slug(self, instance):
        """Get slug"""
        return instance.organization.slug

    class Meta:
        """Meta opts for the serializer."""

        model = UserOrganization
        fields = [
            "id",
            "name",
            "description",
            "logo",
            "slug",
            "contracts",
        ]
        read_only_fields = [
            "id",
            "name",
            "description",
            "logo",
            "slug",
            "contracts",
        ]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for users"""

    # password is explicitly write_only
    password = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(required=False, allow_null=True)
    username = serializers.CharField(
        source="edx_username",
        required=False,
        allow_null=True,
        max_length=OPENEDX_USERNAME_MAX_LEN,
    )
    legal_address = LegalAddressSerializer(allow_null=True)
    user_profile = UserProfileSerializer(allow_null=True, required=False)
    grants = serializers.SerializerMethodField(read_only=True, required=False)
    is_active = serializers.BooleanField(default=True)
    b2b_organizations = serializers.SerializerMethodField()
    is_anonymous = serializers.BooleanField(read_only=True)
    is_authenticated = serializers.BooleanField(read_only=True)

    def validate_email(self, value):
        if (
            not self.instance
            and User.objects.filter(email__iexact=value.strip().lower()).exists()
        ):
            raise serializers.ValidationError(EMAIL_ERROR_MSG)

        return value

    def validate_username(self, value):
        trimmed_value = value.strip()
        if not re.fullmatch(USERNAME_RE, trimmed_value):
            raise serializers.ValidationError(USERNAME_ERROR_MSG)
        return trimmed_value

    @extend_schema_field(list[str])
    def get_grants(self, instance):
        return instance.get_all_permissions()

    @extend_schema_field(UserOrganizationSerializer(many=True))
    def get_b2b_organizations(self, instance):
        """Get the organizations for the user"""
        if instance.is_anonymous:
            return []

        organizations = instance.b2b_organizations
        return UserOrganizationSerializer(
            organizations, many=True, context={"user": instance}
        ).data

    def validate(self, data):
        request = self.context.get("request", None)
        if request is not None and request.method == "POST":
            if not data.get("password"):
                raise serializers.ValidationError(
                    {"password": "This field is required."}
                )
            if not data.get("edx_username"):
                raise serializers.ValidationError(
                    {"username": "This field is required."}
                )

        username = data.get("edx_username")
        email = data.get("email")

        if username:
            # Local duplicate check
            if (
                not self.instance
                and OpenEdxUser.objects.filter(edx_username__iexact=username).exists()
            ):
                raise serializers.ValidationError(
                    {
                        "username": "A user already exists with this username. Please try a different one."
                    }
                )

            # Open edX username/email validation
            try:
                openedx_validation_msg_dict = validate_username_email_with_edx(
                    username, email
                )
            except (
                HTTPError,
                RequestsConnectionError,
                EdxApiRegistrationValidationException,
            ) as exc:
                log.exception("Unable to create user account")
                raise serializers.ValidationError(USER_REGISTRATION_FAILED_MSG) from exc

            if openedx_validation_msg_dict["username"]:
                raise serializers.ValidationError(
                    {
                        "username": OPENEDX_ACCOUNT_CREATION_VALIDATION_MSGS_MAP.get(
                            openedx_validation_msg_dict["username"]
                        )
                    }
                )

            if openedx_validation_msg_dict["email"]:
                raise serializers.ValidationError(
                    {"email": openedx_validation_msg_dict["email"]}
                )

        return data

    def create(self, validated_data):
        """Create a new user"""
        legal_address_data = validated_data.pop("legal_address")
        user_profile_data = validated_data.pop("user_profile", None)

        username = validated_data.pop("edx_username")
        email = validated_data.pop("email")
        password = validated_data.pop("password")

        with transaction.atomic():
            user = User.objects.create_user(
                username,
                email=email,
                password=password,
                **validated_data,
            )

            # this side-effects such that user.legal_address and user.profile are updated in-place
            if legal_address_data:
                legal_address = LegalAddressSerializer(
                    user.legal_address, data=legal_address_data
                )
                if legal_address.is_valid():
                    legal_address.save()

            if user_profile_data:
                user_profile = UserProfileSerializer(
                    user.user_profile, data=user_profile_data
                )
                if user_profile.is_valid():
                    user_profile.save()

        sync_hubspot_user(user)
        return user

    def update(self, instance, validated_data):
        """Update an existing user"""
        legal_address_data = validated_data.pop("legal_address", None)
        user_profile_data = validated_data.pop("user_profile", None)
        password = validated_data.pop("password", None)

        with transaction.atomic():
            # this side-effects such that user.legal_address is updated in-place
            if legal_address_data:
                address_serializer = LegalAddressSerializer(
                    instance.legal_address, data=legal_address_data
                )
                if address_serializer.is_valid(raise_exception=True):
                    address_serializer.save()

            if user_profile_data:
                if user_profile_data.get("highest_education") and (
                    user_profile_data.get("type_is_student")
                    or user_profile_data.get("type_is_professional")
                    or user_profile_data.get("type_is_educator")
                    or user_profile_data.get("type_is_other")
                ):
                    user_profile_data["addl_field_flag"] = True
                else:
                    user_profile_data["addl_field_flag"] = False

                try:
                    user_profile_serializer = UserProfileSerializer(
                        instance.user_profile, data=user_profile_data
                    )
                except:  # noqa: E722
                    user_profile_serializer = UserProfileSerializer(
                        UserProfile(user=instance), data=user_profile_data
                    )

                if user_profile_serializer.is_valid(raise_exception=True):
                    user_profile_serializer.save()

            # clear openedx error data to give this another chance to sync
            instance.openedx_users.update(has_sync_error=False, sync_error_data=None)

            # save() will be called in super().update()
            if password is not None:
                instance.set_password(password)

            user = super().update(instance, validated_data)

        return user  # noqa: RET504

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "name",
            "email",
            "password",
            "legal_address",
            "user_profile",
            "is_anonymous",
            "is_authenticated",
            "is_editor",
            "is_staff",
            "is_superuser",
            "created_on",
            "updated_on",
            "grants",
            "is_active",
            "b2b_organizations",
        )
        read_only_fields = (
            "is_anonymous",
            "is_authenticated",
            "is_editor",
            "is_staff",
            "is_superuser",
            "created_on",
            "updated_on",
            "grants",
            "global_id",
            "b2b_organizations",
        )


class ChangeEmailRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for starting a user email change"""

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    new_email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Validate the change request"""
        # verify no other user has this email address
        errors = {}

        user = attrs["user"]
        new_email = attrs["new_email"]
        password = attrs.pop("password")

        if user.email == new_email:
            # verify the user isn't trying to change their email to their current one
            # this would indicate a programming error on the frontend if this request is allowed
            errors["email"] = "Provided email address is same as your current one"
        elif User.objects.filter(email=new_email).exists():
            errors["email"] = "Invalid email address"

        if errors:
            raise serializers.ValidationError(errors)

        # verify the password verifies for the current user
        if not user.check_password(password):
            raise serializers.ValidationError("Invalid Password")  # noqa: EM101

        return attrs

    def create(self, validated_data):
        """Create the email change request"""
        change_request = super().create(validated_data)

        verification_api.send_verify_email_change_email(
            self.context["request"], change_request
        )

        return change_request

    class Meta:
        model = ChangeEmailRequest

        fields = ("user", "new_email", "password")


class ChangeEmailRequestUpdateSerializer(serializers.ModelSerializer):
    """Serializer for confirming a user email change"""

    confirmed = serializers.BooleanField()

    @transaction.atomic
    def update(self, instance, validated_data):
        """Updates an email change request"""
        if User.objects.filter(email__iexact=instance.new_email).exists():
            log.debug(
                "User %s tried to change email address to one already in use", instance
            )
            raise serializers.ValidationError("Unable to change email")  # noqa: EM101

        result = super().update(instance, validated_data)

        # change request has been confirmed
        if result.confirmed:
            user = result.user
            old_email = user.email
            user.email = result.new_email
            user.save()
            # delete social_auth entry to avoid old email account access
            try:
                user_social_auth = UserSocialAuth.objects.get(uid=old_email, user=user)
                user_social_auth.delete()
            except UserSocialAuth.DoesNotExist:
                pass
            change_edx_user_email_async.delay(user.id)

        return result

    class Meta:
        model = ChangeEmailRequest

        fields = ("confirmed",)


class StateProvinceSerializer(serializers.Serializer):
    """Serializer for pycountry states/provinces"""

    code = serializers.CharField()
    name = serializers.CharField()


class CountrySerializer(serializers.Serializer):
    """Serializer for pycountry countries, with states for US/CA"""

    code = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    states = serializers.SerializerMethodField()

    @extend_schema_field(str)
    def get_code(self, instance) -> str:
        """Get the country alpha_2 code"""
        return instance.alpha_2

    @extend_schema_field(str)
    def get_name(self, instance) -> str:
        """Get the country name (common name preferred if available)"""
        if hasattr(instance, "common_name"):
            return instance.common_name
        return instance.name

    @extend_schema_field(list[dict])
    def get_states(self, instance) -> list[dict]:
        """Get a list of states/provinces if USA or Canada"""
        if instance.alpha_2 in ("US", "CA"):
            return StateProvinceSerializer(
                instance=sorted(
                    pycountry.subdivisions.get(country_code=instance.alpha_2),
                    key=lambda state: state.name,
                ),
                many=True,
            ).data
        return []
