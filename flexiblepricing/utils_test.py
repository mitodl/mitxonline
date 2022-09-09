import pytest
import factory

from flexiblepricing.utils import ensure_flexprice_form_fields
from cms.factories import FlexiblePricingFormFactory
from cms.models import FormField

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def flex_price_form():
    return FlexiblePricingFormFactory.create()


def test_form_with_no_fields(flex_price_form):
    """
    Tests a form that has no fields defined in it at all. This is the default
    state of a form created by the factory; if that changes then this test also
    needs to change.
    """

    assert flex_price_form.form_fields.count() == 0

    assert ensure_flexprice_form_fields(flex_price_form) is False

    flex_price_form.refresh_from_db()

    assert flex_price_form.form_fields.count() == 2

    for field in flex_price_form.form_fields.all():
        assert (
            field.clean_name == "income_currency" or field.clean_name == "your_income"
        )


@pytest.mark.parametrize("field_type", ["income", "currency"])
def test_form_with_misnamed_fields(flex_price_form, field_type):
    """
    Tests a form that has a field with clean_name set right but the label isn't.
    This should still work and the defined field should be left alone.
    """

    assert flex_price_form.form_fields.count() == 0

    new_field = FormField(
        page=flex_price_form,
        required=True,
        label=factory.fuzzy.FuzzyText("Form Field "),
    )

    if field_type == "income":
        new_field.clean_name = "your_income"
        new_field.field_type = "number"
    else:
        new_field.clean_name = "income_currency"
        new_field.field_type = "country"

    new_field.save()
    new_field.refresh_from_db()

    flex_price_form.refresh_from_db()

    assert ensure_flexprice_form_fields(flex_price_form) is False

    for field in flex_price_form.form_fields.all():
        if field == new_field:
            assert field.clean_name == new_field.clean_name
            assert field.label == new_field.label


def test_form_with_proper_fields(flex_price_form):
    """
    Tests a form that has the fields already in it as it should.
    """

    FormField.objects.create(
        page=flex_price_form,
        clean_name="your_income",
        label="Your Income",
        field_type="number",
        required=True,
    )

    FormField.objects.create(
        page=flex_price_form,
        clean_name="income_currency",
        label="Income Currency",
        field_type="country",
        required=True,
    )

    assert ensure_flexprice_form_fields(flex_price_form) is True
