"""User serializers"""
import logging
import re
from collections import defaultdict

import pycountry
from django.db import transaction
from requests import HTTPError
from requests.exceptions import ConnectionError as RequestsConnectionError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from social_django.models import UserSocialAuth

from hubspot_sync.task_helpers import sync_hubspot_user

# from ecommerce.api import fetch_and_serialize_unused_coupons
from mail import verification_api
from main.constants import USER_REGISTRATION_FAILED_MSG
from main.serializers import WriteableSerializerMethodField
from openedx.api import validate_username_with_edx
from openedx.exceptions import EdxApiRegistrationValidationException
from openedx.tasks import change_edx_user_email_async
from users.models import ChangeEmailRequest, LegalAddress, UserProfile, User

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

OPENEDX_USERNAME_VALIDATION_MSGS_MAP = {
    "It looks like this username is already taken": USERNAME_ALREADY_EXISTS_MSG
}


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for profile"""
    gender = serializers.CharField(max_length=128)
    year_of_birth = serializers.IntegerField()

    class Meta:
        model = UserProfile
        fields = {
            "gender",
            "year_of_birth",
        }


class LegalAddressSerializer(serializers.ModelSerializer):
    """Serializer for legal address"""

    # NOTE: the model defines these as allowing empty values for backwards compatibility
    #       so we override them here to require them for new writes
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)
    country = serializers.CharField(max_length=2)
    state = serializers.CharField(max_length=10)

    def validate_first_name(self, value):
        """Validates the first name of the user"""
        if value and not USER_GIVEN_NAME_RE.match(value):
            raise serializers.ValidationError("First name is not valid")
        return value

    def validate_last_name(self, value):
        """Validates the last name of the user"""
        if value and not USER_GIVEN_NAME_RE.match(value):
            raise serializers.ValidationError("Last name is not valid")
        return value

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

    def get_email(self, instance):
        """Get email from the linked user object"""
        return instance.user.email

    class Meta:
        model = LegalAddress
        fields = LegalAddressSerializer.Meta.fields + ("email",)


class PublicUserSerializer(serializers.ModelSerializer):
    """Serializer for public user data"""

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


class UserSerializer(serializers.ModelSerializer):
    """Serializer for users"""

    # password is explicitly write_only
    password = serializers.CharField(write_only=True, required=False)
    email = WriteableSerializerMethodField()
    username = serializers.CharField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message=USERNAME_ALREADY_EXISTS_MSG,
                lookup="iexact",
            )
        ],
        required=False,
    )
    legal_address = LegalAddressSerializer(allow_null=True)
    user_profile = UserProfileSerializer(allow_null=True, required=False)
    grants = serializers.SerializerMethodField(read_only=True, required=False)

    def validate_email(self, value):
        """Empty validation function, but this is required for WriteableSerializerMethodField"""
        return {"email": value}

    def validate_username(self, value):
        """Validates the username field"""
        trimmed_value = value.strip()
        if not re.fullmatch(USERNAME_RE, trimmed_value):
            raise serializers.ValidationError(USERNAME_ERROR_MSG)

        return trimmed_value

    def get_email(self, instance):
        """Returns the email or None in the case of AnonymousUser"""
        return getattr(instance, "email", None)

    def get_username(self, instance):
        """Returns the username or None in the case of AnonymousUser"""
        return getattr(instance, "username", None)

    def get_grants(self, instance):
        return instance.get_all_permissions()

    def validate(self, data):
        request = self.context.get("request", None)
        # Certain fields are required only if a new User is being created (i.e.: the request method is POST)
        if request is not None and request.method == "POST":
            if not data.get("password"):
                raise serializers.ValidationError(
                    {"password": "This field is required."}
                )
            if not data.get("username"):
                raise serializers.ValidationError(
                    {"username": "This field is required."}
                )

        username = data.get("username")
        if username:
            try:
                openedx_validation_msg = validate_username_with_edx(username)
                openedx_validation_msg = OPENEDX_USERNAME_VALIDATION_MSGS_MAP.get(
                    openedx_validation_msg, openedx_validation_msg
                )
            except (
                HTTPError,
                RequestsConnectionError,
                EdxApiRegistrationValidationException,
            ) as exc:
                log.exception("Unable to create user account", exc)
                raise serializers.ValidationError(USER_REGISTRATION_FAILED_MSG)

            if openedx_validation_msg:
                raise serializers.ValidationError({"username": openedx_validation_msg})

        return data

    def create(self, validated_data):
        """Create a new user"""
        legal_address_data = validated_data.pop("legal_address")
        user_profile_data = validated_data.pop("profile", None)

        username = validated_data.pop("username")
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
                user_profile = UserProfileSerializer(user.user_profile, data=user_profile_data)
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
                user_profile_serializer = UserProfileSerializer(instance.user_profile, data=user_profile_data)
                if user_profile_serializer.is_valid(raise_exception=True):
                    user_profile_serializer.save()

            # save() will be called in super().update()
            if password is not None:
                instance.set_password(password)

            user = super().update(instance, validated_data)

        sync_hubspot_user(user)
        return user

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
        )
        read_only_fields = (
            "username",
            "is_anonymous",
            "is_authenticated",
            "is_editor",
            "is_staff",
            "is_superuser",
            "created_on",
            "updated_on",
            "grants",
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
            raise serializers.ValidationError("Invalid Password")

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
        if User.objects.filter(email=instance.new_email).exists():
            log.debug(
                "User %s tried to change email address to one already in use", instance
            )
            raise serializers.ValidationError("Unable to change email")

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

    def get_code(self, instance):
        """Get the country alpha_2 code"""
        return instance.alpha_2

    def get_name(self, instance):
        """Get the country name (common name preferred if available)"""
        if hasattr(instance, "common_name"):
            return instance.common_name
        return instance.name

    def get_states(self, instance):
        """Get a list of states/provinces if USA or Canada"""
        if instance.alpha_2 in ("US", "CA"):
            return StateProvinceSerializer(
                instance=sorted(
                    list(pycountry.subdivisions.get(country_code=instance.alpha_2)),
                    key=lambda state: state.name,
                ),
                many=True,
            ).data
        return []
