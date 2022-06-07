from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from mitol.common.utils.datetime import now_in_utc

from flexiblepricing import models
from flexiblepricing.api import (
    determine_income_usd,
    determine_auto_approval,
)
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.exceptions import NotSupportedException
from users.serializers import UserSerializer


class CurrencyExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CurrencyExchangeRate
        fields = [
            "id",
            "currency_code",
            "exchange_rate",
        ]


class CountryIncomeThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CountryIncomeThreshold
        fields = ["id", "country_code", "income_threshold"]


class FlexiblePriceSerializer(serializers.ModelSerializer):
    """
    Serializer for flexible price requests
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = models.FlexiblePrice
        fields = [
            "id",
            "user",
            "status",
            "income_usd",
            "original_income",
            "original_currency",
            "country_of_income",
            "date_exchange_rate",
            "date_documents_sent",
            "justification",
            "country_of_residence",
        ]
