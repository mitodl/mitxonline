"""
MITxOnline Flexible Pricing/Financial Aid views
"""
from rest_framework import mixins, status
from rest_framework.viewsets import ModelViewSet
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from main.views import RefinePagination
from django.db.models import Q

from flexiblepricing import models, serializers


class CurrencyExchangeRateViewSet(ModelViewSet):
    queryset = models.CurrencyExchangeRate.objects.all()
    serializer_class = serializers.CurrencyExchangeRateSerializer
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)


class CountryIncomeThresholdViewSet(ModelViewSet):
    queryset = models.CountryIncomeThreshold.objects.all()
    serializer_class = serializers.CountryIncomeThresholdSerializer
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)


class FlexiblePriceViewSet(ModelViewSet):
    serializer_class = serializers.FlexiblePriceSerializer
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)
    pagination_class = RefinePagination

    def get_queryset(self):
        return models.FlexiblePrice.objects.filter(user=self.request.user).all()


class FlexiblePriceAdminViewSet(ModelViewSet):
    serializer_class = serializers.FlexiblePriceSerializer
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAdminUser,)
    pagination_class = RefinePagination

    def get_queryset(self):
        queryset = models.FlexiblePrice.objects.all()

        name_search = self.request.query_params.get("q")

        if name_search is not None:
            queryset = queryset.filter(
                Q(user__username__contains=name_search)
                | Q(user__name__contains=name_search)
                | Q(user__email__contains=name_search)
            )

        status_search = self.request.query_params.get("status")

        if status_search is not None:
            queryset = queryset.filter(status=status_search)

        return queryset
