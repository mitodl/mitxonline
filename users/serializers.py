"""User serializers"""
import logging
import re
from collections import defaultdict

import pycountry
from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from social_django.models import UserSocialAuth

# from ecommerce.api import fetch_and_serialize_unused_coupons
from mail import verification_api
from main.serializers import WriteableSerializerMethodField
from openedx.tasks import change_edx_user_email_async
from users.models import ChangeEmailRequest, LegalAddress, Profile, User

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


class LegalAddressSerializer(serializers.ModelSerializer):
    """Serializer for legal address"""

    # NOTE: the model defines these as allowing empty values for backwards compatibility
    #       so we override them here to require them for new writes
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)
    country = serializers.CharField(max_length=2)

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
        )


class PublicUserSerializer(serializers.ModelSerializer):
    """Serializer for public user data"""

    class Meta:
        model = User
        fields = ("id", "username", "name", "created_on", "updated_on")


class UserSerializer(serializers.ModelSerializer):
    """Serializer for users"""

    # password is explicitly write_only
    password = serializers.CharField(write_only=True, required=False)
    email = WriteableSerializerMethodField()
    username = serializers.CharField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="A user already exists with this username. Please try a different one.",
                lookup="iexact",
            )
        ],
        required=False,
    )
    legal_address = LegalAddressSerializer(allow_null=True)

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
        return data

    def create(self, validated_data):
        """Create a new user"""
        legal_address_data = validated_data.pop("legal_address")
        profile_data = validated_data.pop("profile", None)

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

        return user

    def update(self, instance, validated_data):
        """Update an existing user"""
        legal_address_data = validated_data.pop("legal_address", None)
        password = validated_data.pop("password", None)

        with transaction.atomic():
            # this side-effects such that user.legal_address is updated in-place
            if legal_address_data:
                address_serializer = LegalAddressSerializer(
                    instance.legal_address, data=legal_address_data
                )
                if address_serializer.is_valid(raise_exception=True):
                    address_serializer.save()

            # save() will be called in super().update()
            if password is not None:
                instance.set_password(password)

            user = super().update(instance, validated_data)

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
            "is_anonymous",
            "is_authenticated",
            "is_editor",
            "created_on",
            "updated_on",
        )
        read_only_fields = (
            "username",
            "is_anonymous",
            "is_authenticated",
            "is_editor",
            "created_on",
            "updated_on",
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
