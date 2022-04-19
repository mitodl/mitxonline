"""
MITxOnline Flexible Pricing/Financial Aid views
"""
from rest_framework import mixins, status
from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser

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

    def get_queryset(self):
        return models.FlexiblePrice.objects.filter(user=self.request.user).all()


class FlexiblePriceAdminViewSet(ModelViewSet):
    serializer_class = serializers.FlexiblePriceSerializer
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAdminUser,)
    queryset = models.FlexiblePrice.objects.all()
