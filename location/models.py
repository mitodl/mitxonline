"""Models for locations."""

import reversion
from django.db import models
from django_countries.fields import CountryField
from mitol.common.models import TimestampedModel
from mitol.common.utils.datetime import now_in_utc

from location.constants import LOCATION_FLAG_TYPE_CHOICES
from main.models import ValidateOnSaveMixin


class ActiveObjectManager(models.Manager):
    """Query manager for active objects"""

    def get_queryset(self):
        """Getting the active queryset for manager"""
        return super().get_queryset().filter(is_active=True)


class SoftDeleteTimestampedModel(TimestampedModel):
    """Extends TimestampedModel to include a delete date and soft-deletion"""

    deleted_on = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(blank=True, default=True)

    objects = ActiveObjectManager()
    all_objects = models.Manager()

    def clean(self):
        """Ensure the deleted_on field is set if is_active=False."""

        if not self.is_active and not self.deleted_on:
            self.deleted_on = now_in_utc()

        super().clean()

    def delete(self, *_):
        """Disallow deletion; change the is_active flag instead."""

        self.is_active = False
        self.deleted_on = now_in_utc()
        self.save(
            updated_fields=(
                "is_active",
                "deleted_on",
            )
        )


@reversion.register(exclude=("created_on", "updated_on"))
class LocationFlag(SoftDeleteTimestampedModel, ValidateOnSaveMixin):
    """
    Stores locations that are flagged for special processing.

    Not intended to store anything specific about the processing - just that
    processing _should_ happen if there's a flag.
    """

    flag_type = models.CharField(
        help_text="Specifies what processing should happen if flagged.",
        max_length=100,
        blank=True,
        choices=LOCATION_FLAG_TYPE_CHOICES,
        default="",
    )
    prefer_determination_type = models.CharField(
        help_text="Set which determination method should be  "
    )
    country_code = CountryField()
    subdivision_1_code = models.CharField(
        help_text="ISO-3166-2 code for the first-level subdivison of the Country (region/county/etc), without alpha-2 prefix.",
        max_length=3,
        blank=True,
        default="",
    )
    subdivision_2_code = models.CharField(
        help_text="ISO-3166-2 code for the second-level subdivison of the Country (city/town/etc), without alpha-2 prefix.",
        max_length=3,
        blank=True,
        default="",
    )
