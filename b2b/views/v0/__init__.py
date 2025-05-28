"""Views for the B2B API (v0)."""

from rest_framework import viewsets
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
from ecommerce.models import Product


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
    serializer_class = CreateB2BEnrollmentSerializer

    def post(self, request, readable_id: str, format=None):  # noqa: A002, ARG002
        """Create an enrollment for the given course run."""

        courserun = CourseRun.objects.filter(
            readable_id=readable_id, b2b_contract__isnull=False
        ).get()
        product = Product.objects.filter(purchasable_object_id=courserun.id).get()

        return Response(
            CreateB2BEnrollmentSerializer(create_b2b_enrollment(request, product)).data
        )
