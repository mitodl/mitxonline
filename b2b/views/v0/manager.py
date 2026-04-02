"""B2B manager dashboard views."""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin

from b2b.constants import CONTRACT_MEMBERSHIP_AUTOS
from b2b.models import (
    ContractPage,
    OrganizationPage,
)
from b2b.permissions import IsOrganizationManager
from b2b.serializers.v0 import (
    BaseContractPageSerializer,
    OrganizationPageSerializer,
)
from b2b.serializers.v0.manager import (
    ManagerContractDetailSerializer,
    ManagerCourseRunSerializer,
    ManagerEnrollmentCodeSerializer,
    ManagerEnrollmentSerializer,
)
from courses.models import CourseRun, CourseRunEnrollment


class ManagerOrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    """List organizations available for the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationPageSerializer

    def get_queryset(self):
        """Filter to organizations where the user is a manager."""
        return (
            OrganizationPage.objects.distinct()
            if self.request.user and self.request.user.is_superuser
            else OrganizationPage.objects.filter(
                organization_users__user=self.request.user,
                organization_users__is_manager=True,
            ).distinct()
        )

    @extend_schema(
        operation_id="b2b_manager_organizations_list",
        description="List managed organizations",
    )
    def list(self, request, *args, **kwargs):
        """List the orgs."""

        return super().list(request, *args, **kwargs)

    @extend_schema(
        operation_id="b2b_manager_organizations_detail",
        description="Retrieve managed organizations",
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID of the organization",
                required=True,
            ),
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve an org."""

        return super().retrieve(request, *args, **kwargs)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="parent_lookup_organization",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the parent organization",
            required=True,
        ),
        OpenApiParameter(
            name="id",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the contract",
            required=True,
        ),
    ]
)
class ManagerContractViewSet(NestedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """List an organization's contracts."""

    permission_classes = [IsAuthenticated, IsOrganizationManager]
    queryset = ContractPage.objects.select_related("organization")

    def get_serializer_class(self):
        """Use different serializers for list vs detail views."""
        if self.action == "list":
            return BaseContractPageSerializer
        return ManagerContractDetailSerializer

    @action(detail=True, methods=["get"])
    def course_runs(self, request, **kwargs):  # noqa: ARG002
        """
        List course runs available for a specific contract.

        GET /api/v0/b2b/orgs/{org_id}/manager/contracts/{contract_id}/course_runs/
        """
        contract = self.get_object()
        course_runs = contract.get_course_runs()
        serializer = ManagerCourseRunSerializer(course_runs, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="course_run_id",
                type=str,
                location=OpenApiParameter.PATH,
                description="Courseware ID to pull enrollments for.",
                required=True,
            ),
        ],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="course_runs/(?P<course_run_id>[^/.]+)/enrollments",
    )
    def course_run_enrollments(self, request, **kwargs):  # noqa: ARG002
        """List enrollments for a specific course run within a contract."""
        contract = self.get_object()
        course_run_id = kwargs.pop("course_run_id")

        # Get the course run and verify it belongs to this contract
        course_run = get_object_or_404(
            CourseRun, courseware_id=course_run_id, b2b_contract=contract
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
    def codes(self, request, **kwargs):  # noqa: ARG002
        """
        List enrollment codes for a contract.

        Only shows codes for contracts that require them (non-auto membership types).
        Logic varies based on whether contract has learner limits.
        """
        contract = self.get_object()

        # Skip if contract has auto membership type (no codes needed)
        if contract.membership_type in CONTRACT_MEMBERSHIP_AUTOS:
            return Response([])

        discounts = contract.get_discounts()

        if not contract.max_learners:
            # No learner limit - show first code only, if there is one
            return Response(
                ManagerEnrollmentCodeSerializer(
                    [discounts.order_by("id").first()],
                    context={"contract": contract},
                    many=True,
                )
            )

        else:
            # Has learner limit - show redeemed codes + enough unused codes to fill remaining seats
            discounts = discounts.annotate(
                num_redemptions=Count("contract_redemptions")
            ).order_by("-num_redemptions", "id")

            codes_for_output = discounts.filter(num_redemptions__gt=0).all()

            # The point of this is to ensure we always get _all_ the redeemed
            # codes, and then some unredeemed ones if there's space allowed.
            # I didn't want to just call all() and grab a slice because we might
            # have _more_ redemptions that we technically allow (if, say, we
            # adjust the limit down or manually create some redemptions or
            # something).

            if codes_for_output.count() < contract.max_learners:
                # We have seats available, so grab some more codes.
                codes_for_output = discounts.all()[: contract.max_learners]

            return Response(
                ManagerEnrollmentCodeSerializer(
                    codes_for_output, many=True, context={"contract": contract}
                ).data
            )
