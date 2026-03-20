"""Courses v3 serializers"""

from __future__ import annotations

import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from courses import models
from courses.api import create_run_enrollments
from courses.serializers.v1.base import (
    BaseCourseRunEnrollmentSerializer,
    BaseCourseRunSerializer,
    BaseCourseSerializer,
)
from courses.serializers.v3.certificates import CourseRunCertificateSerializer
from main import features

log = logging.getLogger(__name__)


@extend_schema_serializer(component_name="CourseV3")
class CourseSerializer(BaseCourseSerializer):
    """Course serializer"""

    class Meta(BaseCourseSerializer.Meta):
        fields = [
            *BaseCourseSerializer.Meta.fields,
            "include_in_learn_catalog",
        ]


@extend_schema_serializer(component_name="CourseRunWithCourseV3")
class CourseRunWithCourseSerializer(BaseCourseRunSerializer):
    """CourseRun serializer"""

    course = CourseSerializer(read_only=True)
    upgrade_product_id = serializers.SerializerMethodField()
    upgrade_product_price = serializers.SerializerMethodField()
    upgrade_product_is_active = serializers.SerializerMethodField()

    def _get_upgrade_product(self, obj):
        """Return the active upgrade product only if the run is currently upgradable."""
        if not obj.is_upgradable:
            return None

        prefetched_products = getattr(obj, "prefetched_products", None)
        if prefetched_products is not None:
            return prefetched_products[0] if prefetched_products else None

        return (
            obj.products.filter(is_active=True).only("id", "price", "is_active").first()
        )

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_upgrade_product_id(self, obj):
        product = self._get_upgrade_product(obj)
        return product.id if product else None

    @extend_schema_field(
        serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    )
    def get_upgrade_product_price(self, obj):
        product = self._get_upgrade_product(obj)
        return str(product.price) if product else None

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_upgrade_product_is_active(self, obj):
        product = self._get_upgrade_product(obj)
        return product.is_active if product else None

    class Meta(BaseCourseRunSerializer.Meta):
        fields = [
            *BaseCourseRunSerializer.Meta.fields,
            "upgrade_product_id",
            "upgrade_product_price",
            "upgrade_product_is_active",
            "course",
        ]


@extend_schema_serializer(component_name="CourseRunEnrollmentV3")
class CourseRunEnrollmentSerializer(BaseCourseRunEnrollmentSerializer):
    """CourseRunEnrollment model serializer"""

    run = CourseRunWithCourseSerializer(read_only=True)
    certificate = CourseRunCertificateSerializer(read_only=True, allow_null=True)

    b2b_organization_id = serializers.SerializerMethodField(read_only=True)
    b2b_contract_id = serializers.SerializerMethodField(read_only=True)

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_b2b_organization_id(self, enrollment):
        """Get the B2B organization ID if this enrollment is associated with a B2B contract."""
        if enrollment.run.b2b_contract:
            return enrollment.run.b2b_contract.organization_id
        return None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_b2b_contract_id(self, enrollment):
        """Get the B2B contract ID if this enrollment is associated with a B2B contract."""
        return enrollment.run.b2b_contract_id

    def create(self, validated_data):
        """Create a new course run enrollment."""
        user = self.context["user"]
        run_id = validated_data["run_id"]
        run = models.CourseRun.objects.filter(id=run_id).first()

        if run is None or run.b2b_contract_id is not None:
            raise ValidationError({"run_id": f"Invalid course run id: {run_id}"})

        successful_enrollments, _ = create_run_enrollments(
            user,
            [run],
            keep_failed_enrollments=settings.FEATURES.get(
                features.IGNORE_EDX_FAILURES, False
            ),
        )
        if not successful_enrollments:
            msg = "Unable to create course run enrollment"
            raise ValueError(msg)

        return successful_enrollments[0]

    class Meta(BaseCourseRunEnrollmentSerializer.Meta):
        model = models.CourseRunEnrollment
        fields = [
            *BaseCourseRunEnrollmentSerializer.Meta.fields,
            "run",
            "b2b_organization_id",
            "b2b_contract_id",
            "certificate",
        ]
