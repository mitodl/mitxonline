"""
Admin views for flexible pricing app
"""

from django.contrib import admin
from reversion.admin import VersionAdmin

from flexiblepricing.models import (
    CountryIncomeThreshold,
    CurrencyExchangeRate,
    FlexiblePrice,
    FlexiblePricingRequestSubmission,
    FlexiblePriceTier,
)


@admin.register(CurrencyExchangeRate)
class CurrencyExchangeRateAdmin(admin.ModelAdmin):
    model = CurrencyExchangeRate


class CountryIncomeThresholdAdmin(admin.ModelAdmin):
    """Admin for CountryIncomeThreshold"""

    model = CountryIncomeThreshold
    list_display = ("country_code", "income_threshold")
    ordering = ("country_code",)


@admin.register(FlexiblePrice)
class FlexiblePriceAdmin(VersionAdmin):
    """Admin for FlexiblePrice"""

    model = FlexiblePrice
    list_display = (
        "id",
        "user",
        "courseware_object_id",
        "courseware_content_type",
        "tier",
    )
    raw_id_fields = ("user",)

    def has_delete_permission(
        self, *args, **kwargs
    ):  # pylint: disable=unused-argument, signature-differs
        return False


@admin.register(FlexiblePricingRequestSubmission)
class FlexiblePricingRequestSubmissionAdmin(admin.ModelAdmin):
    model = FlexiblePricingRequestSubmission
    readonly_fields = ("form_data", "user", "page", "submit_time")


class FlexiblePriceTierAdmin(admin.ModelAdmin):
    """Admin for FlexiblePriceTier"""

    model = FlexiblePriceTier
    list_display = (
        "id",
        "courseware_object_id",
        "courseware_content_type",
        "discount",
        "income_threshold_usd",
        "current",
    )
    raw_id_fields = ("discount",)


admin.site.register(CountryIncomeThreshold, CountryIncomeThresholdAdmin)
admin.site.register(FlexiblePriceTier, FlexiblePriceTierAdmin)
