from django.db import models
import reversion
from rest_framework.exceptions import ValidationError

from main.utils import serialize_model_object
from main.settings import AUTH_USER_MODEL
from ecommerce.models import TimestampedModel
from flexiblepricing.constants import FlexiblePriceStatus


class CurrencyExchangeRate(TimestampedModel):
    """
    Table of currency exchange rates for converting foreign currencies into USD
    """

    currency_code = models.CharField(null=False, unique=True, max_length=3)
    exchange_rate = models.DecimalField(
        null=False,
        decimal_places=3,
        max_digits=4,
        help_text="Indexed to USD at the time the record was created.",
    )  # how much foreign currency is per 1 USD


class CountryIncomeThreshold(TimestampedModel):
    """
    Table of country income thresholds for flexible pricing auto approval
    """

    country_code = models.CharField(null=False, unique=True, max_length=2)
    income_threshold = models.IntegerField(null=False)


@reversion.register()
class FlexiblePrice(TimestampedModel):
    """
    An application for flexible pricing
    """

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
    country_of_residence = models.TextField()

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
