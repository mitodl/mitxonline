"""Views for the B2B API (v0)."""

import logging

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Prefetch, Q
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    inline_serializer,
)
from mitol.common.utils.datetime import now_in_utc
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from b2b.api import create_b2b_enrollment, process_add_org_membership
from b2b.models import (
    ContractPage,
    ContractProgramItem,
    DiscountContractAttachmentRedemption,
    OrganizationPage,
)
from b2b.serializers.v0 import (
    B2BEnrollRequestSerializer,
    ContractPageSerializer,
    CreateB2BEnrollmentSerializer,
    OrganizationPageSerializer,
)
from courses.models import CourseRun
from courses.serializers.v1.base import BaseCourseRunSerializer
from ecommerce.constants import REDEMPTION_TYPE_UNLIMITED
from ecommerce.models import Discount, Product
from main.authentication import CsrfExemptSessionAuthentication
from main.constants import USER_MSG_TYPE_B2B_ENROLL_SUCCESS
from main.permissions import IsAdminOrReadOnly

log = logging.getLogger(__name__)


class OrganizationPageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for the OrganizationPage model.
    """

    queryset = OrganizationPage.objects.prefetch_related(
        Prefetch(
            "contracts",
            queryset=ContractPage.objects.prefetch_related(
                Prefetch(
                    "contract_programs",
                    queryset=ContractProgramItem.objects.order_by("sort_order"),
                    to_attr="_contract_program_ids",
                )
            ).filter(active=True),
            to_attr="_active_contracts",
        )
    )
    serializer_class = OrganizationPageSerializer
    permission_classes = [IsAdminOrReadOnly | HasAPIKey]
    lookup_field = "slug"
    lookup_url_kwarg = "organization_slug"


class ContractPageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for the ContractPage model.
    """

    serializer_class = ContractPageSerializer
    permission_classes = [IsAdminOrReadOnly | HasAPIKey]
    lookup_field = "slug"
    lookup_url_kwarg = "contract_slug"

    def get_queryset(self):
        """Filter to only return active contracts by default."""
        return ContractPage.active_objects.prefetch_related(
            Prefetch(
                "contract_programs",
                queryset=ContractProgramItem.objects.order_by("sort_order"),
                to_attr="_contract_program_ids",
            )
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="course_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                many=True,
                description="Course ID(s) to use",
            ),
        ],
        responses={
            200: BaseCourseRunSerializer(many=True),
            400: inline_serializer(
                name="ContractPageVariantRunBadRequestSerializer",
                fields={"detail": serializers.CharField()},
            ),
        },
    )
    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def all_variant_runs(self, request, contract_slug: str | None = None):
        """Return the variant runs for a contract."""

        if contract_slug and contract_slug.isdecimal():
            contract = ContractPage.active_objects.filter(pk=contract_slug)
        else:
            contract = ContractPage.active_objects.filter(slug=contract_slug)

        if not contract.exists():
            return Response(
                {"detail": "Invalid contract specified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract = contract.get()

        if (
            not request.user.is_superuser
            and not request.user.b2b_contracts.filter(pk=contract.id).exists()
        ):
            return Response(
                {"detail": "Invalid contract specified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filter_courses = request.query_params.getlist("course_id")

        variant_run_qs = contract.get_all_variant_runs()

        if len(filter_courses) > 0:
            variant_run_qs.filter(course__id__in=filter_courses)

        return Response(BaseCourseRunSerializer(variant_run_qs.all(), many=True).data)


class Enroll(APIView):
    """View for enrolling in a B2B course."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=B2BEnrollRequestSerializer,
        responses=CreateB2BEnrollmentSerializer,
    )
    @csrf_exempt
    def post(self, request, readable_id: str, format=None):  # noqa: A002, ARG002
        """Create an enrollment for the given course run."""

        course_run_content_type = ContentType.objects.get_for_model(CourseRun)
        courserun = CourseRun.objects.filter(
            courseware_id=readable_id, b2b_contract__isnull=False
        ).get()
        product = Product.objects.filter(
            content_type=course_run_content_type, object_id=courserun.id
        ).get()

        # Parse optional program_id from request body
        request_serializer = B2BEnrollRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        program_id = request_serializer.validated_data.get("program_id")

        response = create_b2b_enrollment(request, product, program_id=program_id)

        return Response(
            CreateB2BEnrollmentSerializer(response).data,
            status=status.HTTP_201_CREATED
            if response["result"] == USER_MSG_TYPE_B2B_ENROLL_SUCCESS
            else status.HTTP_406_NOT_ACCEPTABLE,
        )


class AttachContractApi(APIView):
    """View for attaching a user to a B2B contract."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [
        CsrfExemptSessionAuthentication,
    ]

    @extend_schema(
        request=None,
        responses=ContractPageSerializer(many=True),
    )
    def post(self, request, enrollment_code: str, format=None):  # noqa: A002, ARG002
        """
        Use the provided enrollment code to attach the user to a B2B contract.

        This will not create an order, nor will it enroll the user. It will
        attach the user to the contract and log that the code was used for this
        purpose (but will _not_ invalidate the code, since we're not actually
        using it at this point).

        This will respect the activation and expiration dates (of both the contract
        and the discount), and will make sure there's sufficient available seats
        in the contract. It will also make sure the code hasn't been used for
        attachment purposes before.

        If the user is already in the contract, then we skip it.

        Returns:
        - 201: Code successfully redeemed and user attached to new contract(s)
        - 200: Code valid but user already attached to all associated contracts
        - 404: Invalid or expired enrollment code
        - 409: Code valid but no available seats in associated contract(s)
        - list of ContractPageSerializer - the active contract associated with the code
        """
        now = now_in_utc()

        try:
            code = self._get_valid_discount(enrollment_code, now)
        except Discount.DoesNotExist:
            # If no valid discount is found, check whether this code belongs to
            # a contract that is actually full. In that case we want to return
            # 409 (Contract is full) instead of a generic 404.

            log.exception(
                "B2B attach: redeeming code %s but it is not valid", enrollment_code
            )

            fallback_discounts = (
                Discount.objects.filter(
                    Q(activation_date__isnull=True) | Q(activation_date__lte=now)
                )
                .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gte=now))
                .filter(discount_code=enrollment_code)
            )

            for discount in fallback_discounts:
                for contract in (
                    discount.b2b_contracts()
                    .filter(active=True)
                    .exclude(Q(contract_start__gte=now) | Q(contract_end__lt=now))
                ):
                    if contract.is_full():
                        log.error(  # noqa: TRY400
                            "B2B attach: checked contract %s for code %s but it's full",
                            contract,
                            enrollment_code,
                        )
                        return Response(
                            {"detail": "Contract is full."},
                            status=status.HTTP_409_CONFLICT,
                        )

            return Response(
                {"detail": "Invalid or expired enrollment code."},
                status=status.HTTP_404_NOT_FOUND,
            )

        b2b_contract_ids = list(
            code.b2b_contracts()
            .filter(active=True)
            .exclude(Q(contract_start__gte=now) | Q(contract_end__lt=now))
            .values_list("id", flat=True)
        )
        if not b2b_contract_ids:
            # Log an error here. We found a code, but it isn't associated with
            # any active contracts, which is generally confusing for operators.
            log.error(
                "B2B attach: code %s is valid but not associated with any contracts",
                code,
            )
            return Response(
                {"detail": "No contracts found for this code."},
                status=status.HTTP_404_NOT_FOUND,
            )

        contracts = self._get_eligible_contracts(request.user, b2b_contract_ids)

        contracts_attached, contract_full = self._attach_user_to_contracts(
            request.user, contracts, code
        )

        active_code_contract = self._get_active_code_user_contract(
            request.user, b2b_contract_ids, now
        )
        # Keep v0 response signature stable (array payload) for existing clients.
        # When we ship a new API version, switch this endpoint to return a single
        # contract object instead of a one-item list.
        serialized_contracts = (
            [ContractPageSerializer(active_code_contract).data]
            if active_code_contract
            else []
        )

        if contracts_attached:
            return Response(serialized_contracts, status=status.HTTP_201_CREATED)

        if contract_full:
            return Response(
                {"detail": "Contract is full."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(serialized_contracts, status=status.HTTP_200_OK)

    def _get_active_code_user_contract(self, user, contract_ids_for_code, now):
        """Return the user's active contract associated with the redeemed code."""
        return (
            user.b2b_contracts.filter(active=True)
            .exclude(Q(contract_start__gt=now) | Q(contract_end__lt=now))
            .filter(pk__in=contract_ids_for_code)
            .first()
        )

    def _get_valid_discount(self, enrollment_code, now):
        """Return a valid discount for the given enrollment code and time."""
        return (
            Discount.objects.annotate(Count("contract_redemptions"))
            .filter(Q(activation_date__isnull=True) | Q(activation_date__lte=now))
            .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gte=now))
            .filter(
                Q(redemption_type=REDEMPTION_TYPE_UNLIMITED)
                | Q(contract_redemptions__count__lt=1)
            )
            .get(discount_code=enrollment_code)
        )

    def _get_eligible_contracts(self, user, contract_ids_for_code):
        """Return contracts associated with the code that the user can join."""

        return (
            ContractPage.active_objects.filter(pk__in=contract_ids_for_code)
            .exclude(pk__in=user.b2b_contracts.all())
            .all()
        )

    def _attach_user_to_contracts(self, user, contracts, code):
        """Attach the user to eligible contracts and track redemption state."""
        contracts_attached = False
        contract_full = False

        for contract in contracts:
            if contract.is_full():
                log.error(
                    "B2B attach to contract: can't add %s to %s: no open seats",
                    user,
                    contract,
                )
                contract_full = True
                continue

            process_add_org_membership(
                user, contract.organization, keep_until_seen=True
            )
            user.b2b_contracts.add(contract)
            DiscountContractAttachmentRedemption.objects.create(
                user=user, discount=code, contract=contract, redeemed_on=now_in_utc()
            )
            contracts_attached = True

        user.save()

        return contracts_attached, contract_full
