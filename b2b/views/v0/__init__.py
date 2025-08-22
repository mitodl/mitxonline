"""Views for the B2B API (v0)."""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from mitol.common.utils.datetime import now_in_utc
from rest_framework import status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from b2b.api import create_b2b_enrollment
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
from ecommerce.models import Discount, Product
from main.constants import USER_MSG_TYPE_B2B_ENROLL_SUCCESS


class OrganizationPageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for the OrganizationPage model.
    """

    queryset = OrganizationPage.objects.all()
    serializer_class = OrganizationPageSerializer
    permission_classes = [IsAdminUser | HasAPIKey]
    lookup_field = "slug"
    lookup_url_kwarg = "organization_slug"


class ContractPageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for the ContractPage model.
    """

    queryset = ContractPage.objects.all()
    serializer_class = ContractPageSerializer
    permission_classes = [IsAdminUser | HasAPIKey]
    lookup_field = "slug"
    lookup_url_kwarg = "contract_slug"


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

        with transaction.atomic():
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

    @extend_schema(
        request=None,
        responses=ContractPageSerializer(many=True),
    )
    @csrf_exempt
    def post(self, request, enrollment_code: str, format=None):  # noqa: A002, ARG002
        """
        Use the provided enrollment code to attach the user to a B2B contract.

        This will not create an order, nor will it enroll the user. It will
        attach the user to the contract and log that the code was used for this
        purpose (but will _not_ invalidate the code, since we're not actually
        using it at this point).

        This will respect the activation and expiration dates (of both the contract
        and the discount), and will make sure there's sufficient available seats
        in the contract.

        If the user is already in the contract, then we skip it.

        Returns:
        - list of ContractPageSerializer - the contracts for the user
        """

        now = now_in_utc()
        try:
            code = (
                Discount.objects.filter(
                    Q(activation_date__isnull=True) | Q(activation_date__lte=now)
                )
                .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gte=now))
                .get(discount_code=enrollment_code)
            )
        except Discount.DoesNotExist:
            return Response(
                ContractPageSerializer(request.user.b2b_contracts.all(), many=True).data
            )

        contract_ids = list(code.b2b_contracts().values_list("id", flat=True))
        contracts = (
            ContractPage.objects.filter(pk__in=contract_ids)
            .exclude(pk__in=request.user.b2b_contracts.all())
            .exclude(Q(contract_end__lt=now) | Q(contract_start__gt=now))
            .all()
        )

        for contract in contracts:
            if contract.is_full():
                continue

            request.user.b2b_contracts.add(contract)
            DiscountContractAttachmentRedemption.objects.create(
                user=request.user, discount=code, contract=contract
            )

        request.user.save()

        return Response(
            ContractPageSerializer(request.user.b2b_contracts.all(), many=True).data
        )
