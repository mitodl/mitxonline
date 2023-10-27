"""
Course API Views version 2
"""

import logging

import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from courses.models import Program
from courses.serializers.v2 import ProgramSerializer


class Pagination(PageNumberPagination):
    """Paginator class for infinite loading"""

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_on"


class ProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """API viewset for Programs"""

    permission_classes = []

    serializer_class = ProgramSerializer
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["id", "live", "readable_id"]
    queryset = Program.objects.filter().prefetch_related("departments")
