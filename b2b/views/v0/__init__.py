"""Views for the B2B API (v0)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from b2b.models import ContractPage, OrganizationPage
from b2b.serializers.v0 import ContractPageSerializer, OrganizationPageSerializer


class OrganizationPageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for the OrganizationPage model.
    """

    queryset = OrganizationPage.objects.all()
    serializer_class = OrganizationPageSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "slug"
    lookup_url_kwarg = "organization_slug"


class ContractPageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for the ContractPage model.
    """

    queryset = ContractPage.objects.all()
    serializer_class = ContractPageSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "slug"
    lookup_url_kwarg = "contract_slug"
