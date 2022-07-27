import json
import reversion

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from courses.models import Program
from ecommerce.models import Discount
from main.utils import serialize_model_object
from main.settings import AUTH_USER_MODEL
from mitol.common.models import TimestampedModel
from courses.models import Course
from flexiblepricing.constants import FlexiblePriceStatus
from wagtail.contrib.forms.models import (
    AbstractFormSubmission,
)


def valid_courseware_types_list():
    return models.Q(app_label="courses", model="course") | models.Q(
        app_label="courses", model="program"
    )


class CurrencyExchangeRate(TimestampedModel):
    """
    Table of currency exchange rates for converting foreign currencies into USD
    """

    currency_code = models.CharField(null=False, unique=True, max_length=3)
    description = models.CharField(max_length=100, null=True, blank=True)
    exchange_rate = models.FloatField()  # how much foreign currency is per 1 USD

    def __str__(self):
        return "{code}: 1 USD = {rate} {code}".format(
            rate=self.exchange_rate, code=self.currency_code
        )


class CountryIncomeThreshold(TimestampedModel):
    """
    Table of country income thresholds for flexible pricing auto approval
    """

    country_code = models.CharField(null=False, unique=True, max_length=2)
    income_threshold = models.IntegerField(null=False)


class FlexiblePricingRequestSubmission(AbstractFormSubmission):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        formdata = json.loads(self.form_data)
        return "Flexible Pricing request from {user}: annual income {income}".format(
            user=self.user.username, income=formdata["your_income"]
        )


class FlexiblePriceTier(TimestampedModel):
    """
    The tiers for discounted pricing
    """

    valid_courseware_types = valid_courseware_types_list()
    discount = models.ForeignKey(
        Discount,
        null=False,
        related_name="flexible_price_tiers",
        on_delete=models.PROTECT,
    )
    courseware_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, limit_choices_to=valid_courseware_types
    )  # add a filter to limit this to program/course contenttypes
    courseware_object_id = models.PositiveIntegerField()
    courseware_object = GenericForeignKey(
        "courseware_content_type", "courseware_object_id"
    )
    current = models.BooleanField(null=False, default=False)
    income_threshold_usd = models.FloatField(null=False)

    def __str__(self):
        return f"Courseware: {self.courseware_object}, income_threshold={self.income_threshold_usd}, Discount={self.discount}"


@reversion.register()
class FlexiblePrice(TimestampedModel):
    """
    An application for flexible pricing
    """

    valid_courseware_types = valid_courseware_types_list()
    user = models.ForeignKey(AUTH_USER_MODEL, null=False, on_delete=models.CASCADE)
    status = models.CharField(
        null=False,
        choices=[(status, status) for status in FlexiblePriceStatus.ALL_STATUSES],
        default=FlexiblePriceStatus.CREATED,
        max_length=30,
    )
    income_usd = models.FloatField(null=True)
    original_income = models.FloatField(null=True)
    original_currency = models.CharField(null=True, max_length=10)
    country_of_income = models.CharField(null=True, max_length=100)
    date_exchange_rate = models.DateTimeField(null=True)
    date_documents_sent = models.DateField(null=True, blank=True)
    justification = models.TextField(null=True)
    country_of_residence = models.TextField(blank=True)
    cms_submission = models.ForeignKey(
        FlexiblePricingRequestSubmission,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    courseware_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, limit_choices_to=valid_courseware_types
    )
    courseware_object_id = models.PositiveIntegerField()
    courseware_object = GenericForeignKey(
        "courseware_content_type", "courseware_object_id"
    )
    tier = models.ForeignKey(
        FlexiblePriceTier, null=True, blank=True, on_delete=models.CASCADE
    )

    def save(self, *args, **kwargs):  # pylint: disable=signature-differs
        """
        Leaving this in but pulled logic - not sure if flexible pricing will
        apply to an individual course run, a program run, or to the learner in
        MITxOnline
        """
        super().save(*args, **kwargs)

    def to_dict(self):
        return serialize_model_object(self)

    def __str__(self):
        return 'FP for user "{user}" in status "{status}"'.format(
            user=self.user.username, status=self.status
        )

    def is_approved(self):
        return (
            self.status == FlexiblePriceStatus.APPROVED
            or self.status == FlexiblePriceStatus.AUTO_APPROVED
        )

    def is_denied(self):
        return self.status == FlexiblePriceStatus.SKIPPED
    
    def is_reset(self):
        return self.status == FlexiblePriceStatus.RESET
