"""Authentication serializers"""

import logging
import re

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from hubspot_sync.task_helpers import sync_hubspot_user
from openedx.api import create_user
from openedx.constants import OPENEDX_USERNAME_MAX_LEN
from users.serializers import (
    LegalAddressSerializer,
    UserProfileSerializer,
    USERNAME_RE_PARTIAL,
    USERNAME_ERROR_MSG,
)

log = logging.getLogger()
User = get_user_model()


class RegisterDetailsSerializer(serializers.Serializer):
    """Serializer for registration details"""

    name = serializers.CharField(write_only=True)
    username = serializers.CharField(write_only=True)
    legal_address = LegalAddressSerializer(write_only=True)
    user_profile = UserProfileSerializer(write_only=True)

    def validate_username(self, value):
        """Validate username format and length"""
        trimmed_value = value.strip()

        # Check length constraints
        if len(trimmed_value) > OPENEDX_USERNAME_MAX_LEN:
            msg = f"Username must be no more than {OPENEDX_USERNAME_MAX_LEN} characters."
            raise serializers.ValidationError(msg)

        min_username_length = 3
        if len(trimmed_value) < min_username_length:
            msg = "Username must be at least 3 characters."
            raise serializers.ValidationError(msg)

        # Check character constraints using the same pattern as users.serializers
        username_pattern = re.compile(rf"^{USERNAME_RE_PARTIAL}$")
        if not username_pattern.match(trimmed_value):
            raise serializers.ValidationError(USERNAME_ERROR_MSG)

        return trimmed_value

    def create(self, validated_data):
        """Save user legal address and user profile"""
        request = self.context["request"]
        user = request.user
        username = validated_data.pop("username")
        name = validated_data.pop("name")
        legal_address_data = validated_data.pop("legal_address")
        user_profile_data = validated_data.pop("user_profile", None)
        with transaction.atomic():
            user.name = name
            user.save()

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
        create_user(user, username)
        sync_hubspot_user(user)
        return user


class RegisterExtraDetailsSerializer(serializers.Serializer):
    """Serializer for extra registration details"""

    gender = serializers.CharField(write_only=True)
    birth_year = serializers.CharField(write_only=True)
    company = serializers.CharField(write_only=True)
    job_title = serializers.CharField(write_only=True)
    industry = serializers.CharField(write_only=True, allow_blank=True, required=False)
    job_function = serializers.CharField(
        write_only=True, allow_blank=True, required=False
    )
    years_experience = serializers.CharField(
        write_only=True, allow_blank=True, required=False
    )
    company_size = serializers.CharField(
        write_only=True, allow_blank=True, required=False
    )
    leadership_level = serializers.CharField(
        write_only=True, allow_blank=True, required=False
    )
    highest_education = serializers.CharField(
        write_only=True, allow_blank=True, required=False
    )

    def create(self, validated_data):
        """Save user extra details"""
        request = self.context["request"]
        user = request.user
        with transaction.atomic():
            user_profile = UserProfileSerializer(user.user_profile, data=validated_data)
            if user_profile.is_valid():
                user_profile.save()

        sync_hubspot_user(user)
        return user
