"""Models for the variants app."""

import json
import logging

import pycountry
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property
from mitol.common.models import TimestampedModel

from courses.constants import (
    COURSE_VARIANT_INDUSTRY,
    COURSE_VARIANT_LANGUAGE_OVERRIDE,
    COURSE_VARIANT_LENGTH,
)

log = logging.getLogger(__name__)


def valid_variant_objects():
    """Return a Q object of objects that support variants."""
    return models.Q(app_label="courses", model="course") | models.Q(
        app_label="b2b", model="contractpage"
    )


class VariantOptionsModel(models.Model):
    """Mixin for variant option types, so they're the same wherever they're needed."""

    language = models.CharField(
        max_length=8,
        blank=True,
        default="",
        db_index=True,
        help_text=(
            "ISO 639-1 language code for this run "
            "(e.g. 'en', 'zh', 'fr'). Leave blank for unspecified."
        ),
    )
    variant_length = models.CharField(
        max_length=1,
        choices=COURSE_VARIANT_LENGTH,
        blank=True,
        default="",
        db_index=True,
        help_text="Variant: Describes the length of the run (short/long).",
    )
    variant_industry = models.CharField(
        max_length=3,
        choices=COURSE_VARIANT_INDUSTRY,
        blank=True,
        default="",
        db_index=True,
        help_text="Variant: Describes the industry the run is adapted for.",
    )

    class Meta:
        """Set this to abstract."""

        abstract = True

    def clean_language(self):
        """Ensure the language field is set properly."""

        if not self.language or self.language == "":
            return

        if self.language not in COURSE_VARIANT_LANGUAGE_OVERRIDE:
            try:
                pycountry.languages.lookup(self.language)
            except LookupError as lke:
                raise ValidationError("Course language is invalid") from lke  # noqa: EM101

    @cached_property
    def language_label(self) -> str:
        """Return the label for the language, using the override if necessary"""

        if not self.language or self.language == "":
            return ""

        try:
            return (
                COURSE_VARIANT_LANGUAGE_OVERRIDE[self.language]
                if self.language in COURSE_VARIANT_LANGUAGE_OVERRIDE
                else pycountry.languages.lookup(self.language).name
            )
        except LookupError:
            log.exception("Invalid language code for %s", self)
            return "INVALID"


class SupportedVariant(TimestampedModel, VariantOptionsModel):
    """Contains the variants supported by a given object."""

    valid_variant_objects = valid_variant_objects()
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=valid_variant_objects,
    )
    object_id = models.PositiveIntegerField()
    variant_object = GenericForeignKey("content_type", "object_id")

    active = models.BooleanField(
        default=True,
        blank=True,
    )
    b2b_only = models.BooleanField(
        verbose_name="Set if this variant only applies within a B2B context.",
        default=False,
        blank=True,
    )
    default_variant = models.BooleanField(
        verbose_name="Set if this set of options is the default.",
        default=False,
        blank=True,
    )

    class Meta:
        """Meta opts for the model"""

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "object_id",
                    "content_type",
                ],
                condition=models.Q(default_variant=True),
                nulls_distinct=True,
                name="unique_default_primary_per_object",
            ),
        ]

    def __str__(self):
        """Return variant opts as a JSON string."""

        return json.dumps(
            {
                "id": self.pk,
                "content_type": f"{self.content_type.app_label}.{self.content_type.model}",
                "object_id": self.object_id,
                "language": self.language,
                "variant_length": self.variant_length,
                "variant_industry": self.variant_industry,
            }
        )

    def save(
        self,
        force_insert=False,  # noqa: FBT002
        force_update=False,  # noqa: FBT002
        using=None,
        update_fields=None,
    ):
        """Override for save to make it run clean_language."""

        self.clean_language()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
