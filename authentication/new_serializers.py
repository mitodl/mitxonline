"""Authentication serializers"""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponseRedirect
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from hubspot_sync.task_helpers import sync_hubspot_user
from users.serializers import UserSerializer, LegalAddressSerializer, UserProfileSerializer, USERNAME_ALREADY_EXISTS_MSG

log = logging.getLogger()
User = get_user_model()


class RegisterDetailsSerializer(serializers.Serializer):
    """Serializer for registration details"""

    name = serializers.CharField(write_only=True)
    username = serializers.CharField(write_only=True)
    legal_address = LegalAddressSerializer(write_only=True)
    user_profile = UserProfileSerializer(write_only=True)

    def create(self, validated_data):  # noqa: ARG002
        """Save user legal address and user profile"""
        request = self.context["request"]
        user = request.user
        username = validated_data.pop("username")
        name = validated_data.pop("name")
        legal_address_data = validated_data.pop("legal_address")
        user_profile_data = validated_data.pop("user_profile", None)
        with transaction.atomic():
            user.username = username
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
