"""Views for the B2B API (v0)."""

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from b2b.api import create_b2b_enrollment
from b2b.models import ContractPage, OrganizationPage
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

        response = create_b2b_enrollment(request, product)

        return Response(
            CreateB2BEnrollmentSerializer(response).data,
            status=status.HTTP_201_CREATED
            if response["result"] == USER_MSG_TYPE_B2B_ENROLL_SUCCESS
            else status.HTTP_406_NOT_ACCEPTABLE,
        )


class EnrollmentCodeViewSet(viewsets.ReadOnlyModelViewSet):
    """View for checking enrollment codes."""

    serializer_class = OrganizationPageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get the queryset for this use case.

        We only want discount codes that are eligible for redemption and tied to
        a B2B contract.
        """

        return (
            Discount.objects.annotate(
                num_user_redemptions=Count(
                    "order_redemptions__id", filter=Q(redeemed_by=self.request.user)
                )
            )
            .annotate(num_redemptions=Count("order_redemptions__id"))
            .filter(
                Q(num_redemptions=0)
                | Q(Q(num_redemptions__gt=0) & Q(num_user_redemptions__gt=0))
            )
            .filter(
                Q(products__product__content_type__model="courserun")
                & Q(
                    products__product__purchaseable_object_id__in=CourseRun.objects.filter(
                        b2b_contract__isnull=False
                    )
                    .all()
                    .values_list("id", flat=True)
                )
            )
        )
