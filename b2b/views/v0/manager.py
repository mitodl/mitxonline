"""B2B manager dashboard views."""

from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, OuterRef, Prefetch, Q, Subquery
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)
from mitol.common.utils.datetime import now_in_utc
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin

from b2b.constants import CONTRACT_MEMBERSHIP_AUTOS
from b2b.mail import send_enrollment_code_assignment_email
from b2b.models import (
    ContractPage,
    ContractProgramItem,
    DiscountContractAttachmentRedemption,
    OrganizationPage,
)
from b2b.permissions import IsOrganizationManager
from b2b.serializers.v0 import (
    BaseContractPageSerializer,
    OrganizationPageSerializer,
)
from b2b.serializers.v0.manager import (
    AssignRevokeCodeRequestSerializer,
    BulkAssignRequestSerializer,
    BulkAssignResultSerializer,
    DetailErrorSerializer,
    ManagerContractDetailSerializer,
    ManagerCourseRunSerializer,
    ManagerEnrollmentCodeSerializer,
    ManagerEnrollmentSerializer,
)
from courses.models import CourseRun, CourseRunEnrollment
from ecommerce.models import Discount


@dataclass
class CodeAssignment:
    contract: ContractPage
    discount: Discount
    email: str
    name: str
    code: str


def assign_codes_and_send_emails(
    assignments: list[CodeAssignment], assigning_user
) -> None:
    # Use bulk_create for this
    for assignment in assignments:
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=assignment.discount,
            contract=assignment.contract,
            assigned_email=assignment.email,
            assigned_name=assignment.name,
            assigned_by=assigning_user,
            last_reminder_sent_on=now_in_utc(),
        )

        send_enrollment_code_assignment_email(redemption, assignment.code)
        # Set the prefetched_redemptions attribute on the discount so that serializers
        # can return the updated redemption info without needing an extra query.
        assignment.discount.prefetched_redemptions = [redemption]


class ManagerOrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    """List organizations available for the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationPageSerializer

    def get_queryset(self):
        """Filter to organizations where the user is a manager."""

        return (
            OrganizationPage.objects.prefetch_related(
                Prefetch(
                    "contracts",
                    queryset=ContractPage.objects.prefetch_related(
                        Prefetch(
                            "contract_programs",
                            queryset=ContractProgramItem.objects.order_by("sort_order"),
                            to_attr="contract_program_ids",
                        )
                    ).filter(active=True),
                    to_attr="_active_contracts",
                ),
            )
            .filter(
                organization_users__user=self.request.user,
                organization_users__is_manager=True,
            )
            .distinct()
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

    def get_queryset(self):
        """Get the queryset; add some annotations/etc for computed fields"""
        courserun_content_type = ContentType.objects.get_for_model(CourseRun)
        return (
            ContractPage.objects.select_related("organization")
            .prefetch_related("users")
            .annotate(
                discount_count=Count(
                    Subquery(
                        Discount.objects.filter(
                            products__product__is_active=True,
                            products__product__content_type=courserun_content_type,
                            products__product__object_id__in=CourseRun.objects.filter(
                                b2b_contract=OuterRef("pk")
                            ).all(),
                        ).values("id")
                    )
                )
            )
            .annotate(
                enrollment_count=Count(
                    "course_runs__enrollments",
                    filter=Q(course_runs__enrollments__active=True),
                    distinct=True,
                )
            )
            .filter(
                organization__organization_users__user=self.request.user,
                organization__organization_users__is_manager=True,
            )
        )

    def get_serializer_class(self):
        """Use different serializers for list vs detail views."""
        if self.action == "list":
            return BaseContractPageSerializer

        # This is ugly and I'm not a fan. We might want to break the assign/revoke/remind/bulk_assign into their
        # own viewset as long as we can keep the URL structure the same.
        if self.action in (
            "assign_code",
            "revoke_code",
            "send_reminder_for_code_assignment",
        ):
            return AssignRevokeCodeRequestSerializer
        if self.action == "bulk_assign":
            return BulkAssignRequestSerializer
        return ManagerContractDetailSerializer

    @extend_schema(
        responses=ManagerCourseRunSerializer(many=True),
        description="List course runs available for a specific contract.",
    )
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
        responses=ManagerEnrollmentSerializer(many=True),
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

    @extend_schema(
        responses=ManagerEnrollmentCodeSerializer(many=True),
        description="List enrollment codes for a contract. Only shows codes for contracts that require them (non-auto membership types). Logic varies based on whether contract has learner limits.",
    )
    @action(detail=True, methods=["get"])
    def codes(self, request, **kwargs):  # noqa: ARG002
        """
        List enrollment codes for a contract.

        Only shows codes for contracts that require them (non-auto membership types).
        Logic varies based on whether contract has learner limits.

        """
        contract = self.get_object()

        """
        There are three main cases:
        - If the contract has an auto membership type, no codes are needed, so we return an empty list.
        - If the contract does not have a learner limit, we show the first code only.
          We don't show individual redemptions because this case is unlikely to be a useful setup for contracts
        - If the contract has a learner limit, we show all redeemed and assigned codes, plus enough unredeemed codes to fill the remaining seats.
          This ensures that managers can see all the codes that are currently in use, while also seeing some of the unused codes that are available to be redeemed.
        """

        # Skip if contract has auto membership type (no codes needed)
        if contract.membership_type in CONTRACT_MEMBERSHIP_AUTOS:
            return Response([])

        discounts = contract.get_discounts().prefetch_related(
            Prefetch(
                "contract_redemptions",
                queryset=DiscountContractAttachmentRedemption.objects.select_related(
                    "user"
                ).order_by("-created_on")[:1],
                to_attr="prefetched_redemptions",
            )
        )

        if not contract.max_learners:
            # No learner limit - show first code only, if there is one
            return Response(
                ManagerEnrollmentCodeSerializer(
                    [discounts.order_by("id").first()],
                    many=True,
                ).data
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
                ManagerEnrollmentCodeSerializer(codes_for_output, many=True).data
            )

    @extend_schema(
        description="Assign an available enrollment code to an email address and send an invite email.",
        request=AssignRevokeCodeRequestSerializer,
        responses={
            200: ManagerEnrollmentCodeSerializer,
            400: DetailErrorSerializer,
            409: DetailErrorSerializer,
        },
        parameters=[
            OpenApiParameter(
                name="code",
                type=str,
                location=OpenApiParameter.PATH,
                description="The discount code to assign.",
                required=True,
            ),
        ],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="codes/(?P<code>[^/.]+)/assign",
    )
    def assign_code(self, request, **kwargs):
        """
        Assign an enrollment code to an email address.

        POST /api/v0/b2b/orgs/{org_id}/manager/contracts/{contract_id}/codes/{code}/assign/
        """

        """
        This endpoint creates a DiscountContractAttachmentRedemption record to assign the code to the email address, and sends an invite email to the assignee.
        It's worth noting that "assigning" a code mostly just affects the count of seats filled against limits.
        Since we explicitly do not check that a redemption user matches the assigned email and we don't necessarily want to require preassignment
        This feature is mostly useful for tracking who a code is intended for and sending reminder emails, rather than being a strict gate on who can redeem a code.
        """
        contract = self.get_object()
        code = kwargs.get("code")

        serializer = AssignRevokeCodeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Invalid request data."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]
        name = serializer.validated_data.get("name", "")

        discount = contract.get_discounts().filter(discount_code=code).first()
        if not discount:
            return Response(
                {"detail": "Code not found for this contract."},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        if discount.contract_redemptions.exists():
            return Response(
                {"detail": "Code has already been assigned or redeemed."},
                status=http_status.HTTP_409_CONFLICT,
            )

        assignment = CodeAssignment(
            code=code, contract=contract, discount=discount, email=email, name=name
        )
        assign_codes_and_send_emails([assignment], request.user)

        return Response(
            ManagerEnrollmentCodeSerializer(discount).data,
            status=http_status.HTTP_200_OK,
        )

    @extend_schema(
        description="Revoke the assignment for a specific enrollment code, returning it to the unassigned pool.",
        request=AssignRevokeCodeRequestSerializer,
        responses={
            200: ManagerEnrollmentCodeSerializer,
            400: DetailErrorSerializer,
            404: DetailErrorSerializer,
        },
        parameters=[
            OpenApiParameter(
                name="code",
                type=str,
                location=OpenApiParameter.PATH,
                description="The discount code to revoke.",
                required=True,
            ),
        ],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="codes/(?P<code>[^/.]+)/revoke",
    )
    def revoke_code(self, request, **kwargs):
        """
        Revoke the assignment for a specific enrollment code.

        POST /api/v0/b2b/orgs/{org_id}/manager/contracts/{contract_id}/codes/{code}/revoke/
        """

        """
            This endpoint removes the DiscountContractAttachmentRedemption record for the specified code and email address.
        """
        # Need to decide if we want to keep this a POST or not. It's not a restful DELETE operation, but it might still be less confusing that way
        # Also decide if we want to take a name and email - we don't need it technically since these should be unique per code.

        # This will probably need revision in the future. Revoking a code doesn't do anything right now, but we might want to
        # burn a code if it's revoked - this will require product input. This only affects the display on the dash for now.
        contract = self.get_object()
        code = kwargs.get("code")

        serializer = AssignRevokeCodeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Invalid request data."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]

        discount = contract.get_discounts().filter(discount_code=code).first()
        if not discount:
            return Response(
                {"detail": "Code not found for this contract."},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        assignment_record = discount.contract_redemptions.filter(
            assigned_email=email
        ).first()
        if not assignment_record:
            return Response(
                {"detail": "Assignment for email does not exist"},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Need to determine if we need to do other cleanup here.
        assignment_record.delete()

        return Response(
            ManagerEnrollmentCodeSerializer(discount).data,
            status=http_status.HTTP_200_OK,
        )

    @extend_schema(
        description="Send a reminder email to the user assigned to a specific enrollment code who has not yet claimed it.",
        request=AssignRevokeCodeRequestSerializer,
        responses={
            200: ManagerEnrollmentCodeSerializer,
            400: DetailErrorSerializer,
            404: DetailErrorSerializer,
        },
        parameters=[
            OpenApiParameter(
                name="code",
                type=str,
                location=OpenApiParameter.PATH,
                description="The discount code to send a reminder for.",
                required=True,
            ),
        ],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="codes/(?P<code>[^/.]+)/remind",
    )
    def send_reminder_for_code_assignment(self, request, **kwargs):
        """
        Send a reminder email to the assignee of a specific enrollment code.

        POST /api/v0/b2b/orgs/{org_id}/manager/contracts/{contract_id}/codes/{code}/remind/
        """
        contract = self.get_object()
        code = kwargs.get("code")

        serializer = AssignRevokeCodeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Invalid request data."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]

        discount = contract.get_discounts().filter(discount_code=code).first()
        if not discount:
            return Response(
                {"detail": "Code not found for this contract."},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        assignment_record = discount.contract_redemptions.filter(
            assigned_email=email
        ).first()
        if not assignment_record:
            return Response(
                {"detail": "Assignment for email does not exist"},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Just send the email reminder and update the last sent timestamp
        send_enrollment_code_assignment_email(assignment_record, code)
        assignment_record.last_reminder_sent_on = now_in_utc()
        assignment_record.save()

        # Set prefetched_redemptions so the serializer returns the current assignment status.
        discount.prefetched_redemptions = [assignment_record]

        return Response(
            ManagerEnrollmentCodeSerializer(discount).data,
            status=http_status.HTTP_200_OK,
        )

    @extend_schema(
        description="Bulk-assign enrollment codes from a list of (email, name) records. "
        "One available code is assigned per record and an invite email is sent to each "
        "successfully assigned address. Returns lists of assigned codes and any errors.",
        request=BulkAssignRequestSerializer,
        responses={
            200: BulkAssignResultSerializer,
            400: DetailErrorSerializer,
        },
    )
    @action(detail=True, methods=["post"], url_path="codes/bulk_assign")
    def bulk_assign(self, request, **kwargs):  # noqa: ARG002
        """
        Bulk-assign enrollment codes from an uploaded file.

        POST /api/v0/b2b/orgs/{org_id}/manager/contracts/{contract_id}/codes/bulk_assign/
        """
        contract = self.get_object()

        serializer = BulkAssignRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Invalid request data."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        email_assignees = serializer.validated_data

        available_discounts = list(
            contract.get_discounts()
            .filter(contract_redemptions__isnull=True)
            .order_by("id")[: len(email_assignees)]
        )

        assignments = []
        errors = []

        for i, record in enumerate(email_assignees):
            email = record["email"]
            name = record.get("name", "")

            if i < len(available_discounts):
                discount = available_discounts[i]
                assignments.append(
                    CodeAssignment(
                        code=discount.discount_code,
                        contract=contract,
                        discount=discount,
                        email=email,
                        name=name,
                    )
                )
            else:
                errors.append(
                    {"email": email, "name": name, "detail": "No available code."}
                )

        assign_codes_and_send_emails(assignments, request.user)

        return Response(
            {
                "assigned": ManagerEnrollmentCodeSerializer(
                    [a.discount for a in assignments], many=True
                ).data,
                "errors": errors,
            },
            status=http_status.HTTP_200_OK,
        )
