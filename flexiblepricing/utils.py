import logging

from django.db.models import Q

from cms.models import FlexiblePricingRequestForm, FormField
from flexiblepricing.constants import REQUIRED_FLEXIBLE_PRICING_FORM_FIELDS

logger = logging.getLogger(__name__)


def ensure_flexprice_form_fields(form_instance: FlexiblePricingRequestForm):
    """
    Checks the supplied form instance for the proper Flexible Pricing Request Form
    fields and adds them if it needs to, or logs if it gets confused. This is
    meant to be called by the signal receiver (see cms/signalreceivers.py) or by
    a management command.

    Args:
    - form_instance (FlexiblePricingForm) - the form to work on

    Returns:
    - boolean - True if the form was OK, False otherwise
    """

    # Build filter to find all relevant fields
    field_types = [spec["field_type"] for spec in REQUIRED_FLEXIBLE_PRICING_FORM_FIELDS]
    clean_names = [spec["clean_name"] for spec in REQUIRED_FLEXIBLE_PRICING_FORM_FIELDS]

    relevant_fields = form_instance.form_fields.filter(
        Q(field_type__in=field_types) | Q(clean_name__in=clean_names)
    ).all()

    expected_count = len(REQUIRED_FLEXIBLE_PRICING_FORM_FIELDS)
    if len(relevant_fields) != expected_count:
        logger.warning(
            f"Improper length {len(relevant_fields)} returned; was expecting {expected_count}"  # noqa: G004
        )

    # Track which required fields are present
    found_fields = set()
    for field in relevant_fields:
        for spec in REQUIRED_FLEXIBLE_PRICING_FORM_FIELDS:
            if (
                field.clean_name == spec["clean_name"]
                and field.field_type == spec["field_type"]
            ):
                found_fields.add(spec["clean_name"])
                break
            elif field.clean_name == spec["clean_name"]:
                logger.error(
                    f"Field '{field.label}' in form {form_instance} has correct name '{field.clean_name}' but wrong type '{field.field_type}'; expected type '{spec['field_type']}'"  # noqa: G004
                )
                break

    # Check if all required fields are present
    required_names = {
        spec["clean_name"] for spec in REQUIRED_FLEXIBLE_PRICING_FORM_FIELDS
    }
    if found_fields == required_names:
        logger.info(
            f"Flexible Pricing Request Form {form_instance} has the right fields in it"  # noqa: G004
        )
        return True

    # Add missing fields
    # Note: We don't pass clean_name to create() because Wagtail's AbstractFormField.save()
    # auto-generates it from the label for new fields. The clean_name in our spec is only
    # used for matching existing fields.
    missing_fields = required_names - found_fields
    for spec in REQUIRED_FLEXIBLE_PRICING_FORM_FIELDS:
        if spec["clean_name"] in missing_fields:
            FormField.objects.create(
                page=form_instance,
                label=spec["label"],
                field_type=spec["field_type"],
                required=spec["required"],
                sort_order=spec["sort_order"],
            )

    missing_field_names = ", ".join(sorted(missing_fields))
    logger.warning(
        f"Added field(s) to {form_instance}: {missing_field_names}"  # noqa: G004
    )
    return False
