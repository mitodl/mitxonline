"""
MITxOnline Flexible Pricing/Financial Aid views
"""
from django.db import transaction
from django.db.models import Q
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from flexiblepricing import models, serializers
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.tasks import (
    notify_financial_assistance_request_denied_email,
    notify_flexible_price_status_change_email,
)
from main.views import RefinePagination


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
    serializer_class = serializers.FlexiblePriceAdminSerializer
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

        return queryset.order_by("-created_on")

    def update(self, request, *args, **kwargs):
        """Update the flexible pricing status"""
        with transaction.atomic():
            update_result = super().update(request, *args, **kwargs)

            # Send email notification
            financial_assistance_request = self.get_object()
            if financial_assistance_request.status != FlexiblePriceStatus.DENIED:
                notify_flexible_price_status_change_email.delay(
                    financial_assistance_request.id
                )
                return update_result

            email_subject = request.data.get("email_subject", None)
            email_body = request.data.get("email_body", None)
            notify_financial_assistance_request_denied_email.delay(
                financial_assistance_request.id, email_subject, email_body
            )
            return update_result
