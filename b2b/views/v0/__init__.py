"""Views for the B2B API (v0)."""

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from mitol.common.utils.datetime import now_in_utc
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from b2b.api import create_b2b_enrollment, process_add_org_membership
from b2b.models import (
    ContractPage,
    DiscountContractAttachmentRedemption,
    OrganizationPage,
)
from b2b.serializers.v0 import (
    ContractPageSerializer,
    CreateB2BEnrollmentSerializer,
    OrganizationPageSerializer,
)
from courses.models import CourseRun
from ecommerce.constants import REDEMPTION_TYPE_UNLIMITED
from ecommerce.models import Discount, Product
from main.authentication import CsrfExemptSessionAuthentication
from main.constants import USER_MSG_TYPE_B2B_ENROLL_SUCCESS
from main.permissions import IsAdminOrReadOnly


class OrganizationPageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for the OrganizationPage model.
    """

    queryset = OrganizationPage.objects.all()
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
        return ContractPage.objects.filter(active=True).prefetch_related("programs")


class Enroll(APIView):
    """View for enrolling in a B2B course."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
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

        response = create_b2b_enrollment(request, product)

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
        - list of ContractPageSerializer - the contracts for the user
        """
        now = now_in_utc()

        try:
            code = self._get_valid_discount(enrollment_code, now)
        except Discount.DoesNotExist:
            # If no valid discount is found, check whether this code belongs to
            # a contract that is actually full. In that case we want to return
            # 409 (Contract is full) instead of a generic 404.

            fallback_discounts = (
                Discount.objects.filter(
                    Q(activation_date__isnull=True) | Q(activation_date__lte=now)
                )
                .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gte=now))
                .filter(discount_code=enrollment_code)
            )

            for discount in fallback_discounts:
                for contract in discount.b2b_contracts():
                    if not contract.active:
                        continue

                    if contract.contract_start and contract.contract_start > now:
                        continue

                    if contract.contract_end and contract.contract_end < now:
                        continue

                    if contract.is_full():
                        return Response(
                            {"detail": "Contract is full."},
                            status=status.HTTP_409_CONFLICT,
                        )

            return Response(
                {"detail": "Invalid or expired enrollment code."},
                status=status.HTTP_404_NOT_FOUND,
            )

        contracts = self._get_eligible_contracts(request.user, code, now)
        contracts_attached, contract_full = self._attach_user_to_contracts(
            request.user, contracts, code
        )

        active_contracts = self._get_active_user_contracts(request.user, now)
        serialized_contracts = ContractPageSerializer(active_contracts, many=True).data

        if contracts_attached:
            return Response(serialized_contracts, status=status.HTTP_201_CREATED)

        if contract_full:
            return Response(
                {"detail": "Contract is full."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(serialized_contracts, status=status.HTTP_200_OK)

    def _get_active_user_contracts(self, user, now):
        """Return active contracts for a user at the given time."""
        return user.b2b_contracts.filter(active=True).exclude(
            Q(contract_start__gt=now) | Q(contract_end__lt=now)
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

    def _get_eligible_contracts(self, user, code, now):
        """Return contracts associated with the code that the user can join."""
        contract_ids = list(code.b2b_contracts().values_list("id", flat=True))
        return (
            ContractPage.objects.filter(pk__in=contract_ids)
            .exclude(pk__in=user.b2b_contracts.all())
            .exclude(Q(contract_end__lt=now) | Q(contract_start__gt=now))
            .all()
        )

    def _attach_user_to_contracts(self, user, contracts, code):
        """Attach the user to eligible contracts and track redemption state."""
        contracts_attached = False
        contract_full = False

        for contract in contracts:
            if contract.is_full():
                contract_full = True
                continue

            process_add_org_membership(
                user, contract.organization, keep_until_seen=True
            )
            user.b2b_contracts.add(contract)
            DiscountContractAttachmentRedemption.objects.create(
                user=user, discount=code, contract=contract
            )
            contracts_attached = True

        user.save()

        return contracts_attached, contract_full
