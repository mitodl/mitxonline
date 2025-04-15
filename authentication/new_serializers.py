"""Authentication serializers"""

import logging

from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


PARTIAL_PIPELINE_TOKEN_KEY = "partial_pipeline_token"  # noqa: S105

log = logging.getLogger()

User = get_user_model()


class RegisterDetailsSerializer(serializers.Serializer):
    """Serializer for registration details"""

    password = serializers.CharField(min_length=8, write_only=True)
    name = serializers.CharField(write_only=True)

    def create(self, validated_data):  # noqa: ARG002
        """Try to 'save' the request"""
        return super()._authenticate(SocialAuthState.FLOW_REGISTER)


class RegisterExtraDetailsSerializer(serializers.Serializer):
    """Serializer for registration details"""

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

    def create(self, validated_data):  # noqa: ARG002
        """Try to 'save' the request"""
        return super()._authenticate(SocialAuthState.FLOW_REGISTER)
