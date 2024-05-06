import logging

from django.db.models import Q

from cms.models import FlexiblePricingRequestForm, FormField

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

    currency_field = False
    income_field = False

    relevant_fields = form_instance.form_fields.filter(
        Q(field_type__in=["country", "number"])
        | Q(clean_name__in=["your_income", "income_currency"])
    ).all()

    if len(relevant_fields) != 2:  # noqa: PLR2004
        logger.warning(
            f"Improper length {len(relevant_fields)} returned; was expecting 2"  # noqa: G004
        )

    for field in relevant_fields:
        if field.field_type == "country":
            if field.clean_name == "income_currency":
                currency_field = True
                continue
            else:
                logger.error(
                    f"Found a currency field for {form_instance} but its clean name is wrong: {field.clean_name} - {field.label}"  # noqa: G004
                )
                return False

        # Country has a specialized purpose; Number does not, so we ignore any other
        # number field.
        if field.field_type == "number":  # noqa: SIM102
            if field.clean_name == "your_income":
                income_field = True
                continue

    if currency_field and income_field:
        logger.info(
            f"Flexible Pricing Request Form {form_instance} has the right fields in it"  # noqa: G004
        )
        return True

    if not income_field:
        FormField.objects.create(
            page=form_instance,
            clean_name="your_income",
            label="Your Income",
            field_type="number",
            required=True,
            sort_order=1,
        )

    if not currency_field:
        FormField.objects.create(
            page=form_instance,
            clean_name="income_currency",
            label="Income Currency",
            field_type="country",
            required=True,
            sort_order=2,
        )

    logger.warning(
        f"Added {'currency' if not currency_field else ''} {'income' if not income_field else ''} field(s) to {form_instance}"  # noqa: G004
    )
    return False
