from rest_framework import serializers

from flexiblepricing import models


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
