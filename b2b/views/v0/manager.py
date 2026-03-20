"""B2B manager dashboard views."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from b2b.constants import CONTRACT_MEMBERSHIP_AUTOS
from b2b.models import (
    ContractPage,
    DiscountContractAttachmentRedemption,
    OrganizationPage,
    is_organization_manager,
)
from b2b.permissions import IsOrganizationManager
from b2b.serializers.v0.manager import (
    ManagerContractDetailSerializer,
    ManagerContractListSerializer,
    ManagerCourseRunSerializer,
    ManagerEnrollmentCodeSerializer,
    ManagerEnrollmentSerializer,
)
from courses.models import CourseRun, CourseRunEnrollment


class ManagerContractViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for organization managers to view their contracts.

    Provides list and detail views for contracts that the authenticated
    user manages.
    """

    permission_classes = [IsAuthenticated, IsOrganizationManager]

    def get_queryset(self):
        """Filter contracts to only those in organizations the user manages."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            return ContractPage.objects.none()

        # Verify user is manager of this organization
        if not is_organization_manager(self.request.user, org_id):
            return ContractPage.objects.none()

        return ContractPage.objects.filter(
            organization_id=org_id, active=True
        ).select_related("organization")

    def get_serializer_class(self):
        """Use different serializers for list vs detail views."""
        if self.action == "list":
            return ManagerContractListSerializer
        return ManagerContractDetailSerializer

    @action(detail=True, methods=["get"])
    def course_runs(self, request, org_id=None, pk=None):
        """
        List course runs available for a specific contract.

        GET /api/v0/b2b/orgs/{org_id}/manager/contracts/{contract_id}/course_runs/
        """
        contract = self.get_object()
        course_runs = contract.get_course_runs()
        serializer = ManagerCourseRunSerializer(course_runs, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get"],
        url_path="course-runs/(?P<course_run_id>[^/.]+)/enrollments",
    )
    def course_run_enrollments(self, request, org_id=None, pk=None, course_run_id=None):
        """
        List enrollments for a specific course run within a contract.

        GET /api/v0/b2b/orgs/{org_id}/manager/contracts/{contract_id}/course-runs/{course_run_id}/enrollments/
        """
        contract = self.get_object()

        # Get the course run and verify it belongs to this contract
        course_run = get_object_or_404(
            CourseRun, readable_id=course_run_id, b2b_contract=contract
        )

        # Get enrollments for this course run
        enrollments = (
            CourseRunEnrollment.objects.filter(run=course_run)
            .select_related("user")
            .order_by("-created_on")
        )

        serializer = ManagerEnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def codes(self, request, org_id=None, pk=None):
        """
        List enrollment codes for a contract.

        GET /api/v0/b2b/orgs/{org_id}/manager/contracts/{contract_id}/codes/

        Only shows codes for contracts that require them (non-auto membership types).
        Logic varies based on whether contract has learner limits.
        """
        contract = self.get_object()

        # Skip if contract has auto membership type (no codes needed)
        if contract.membership_type in CONTRACT_MEMBERSHIP_AUTOS:
            return Response([])

        discounts = contract.get_discounts().order_by("id")

        if not contract.max_learners:
            # No learner limit - show first code only
            if discounts.exists():
                discount = discounts.first()
                serializer = ManagerEnrollmentCodeSerializer(
                    discount, context={"contract": contract}
                )
                return Response([serializer.data])
            else:
                return Response([])
        else:
            # Has learner limit - show redeemed codes + enough unused codes to fill remaining seats
            attached_count = contract.get_learners().count()
            remaining_seats = contract.max_learners - attached_count

            # Get redeemed codes (used for attachment to this contract)
            redeemed_discount_ids = DiscountContractAttachmentRedemption.objects.filter(
                contract=contract
            ).values_list("discount_id", flat=True)

            redeemed_discounts = discounts.filter(id__in=redeemed_discount_ids)

            # Get unused codes to fill remaining seats
            unused_discounts = discounts.exclude(id__in=redeemed_discount_ids)[
                : max(0, remaining_seats)
            ]

            # Combine redeemed and unused codes
            all_discounts = list(redeemed_discounts) + list(unused_discounts)

            serializer = ManagerEnrollmentCodeSerializer(
                all_discounts, many=True, context={"contract": contract}
            )
            return Response(serializer.data)


class ManagerOrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for organization managers to view basic organization info.

    This provides a way to list organizations the user manages and
    get basic organization details.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter to organizations where the user is a manager."""
        return OrganizationPage.objects.filter(
            organization_users__user=self.request.user,
            organization_users__is_manager=True,
        ).distinct()

    def get_serializer_class(self):
        """Use a simple serializer for organization info."""

        # We can reuse an existing serializer or create a minimal one
        # For now, let's create a simple inline serializer
        class SimpleOrgSerializer(serializers.ModelSerializer):
            class Meta:
                model = OrganizationPage
                fields = ["id", "name", "org_key"]

        return SimpleOrgSerializer
