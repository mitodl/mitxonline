import factory
import pytest

from cms.factories import FlexiblePricingFormFactory
from cms.models import FormField
from flexiblepricing.utils import ensure_flexprice_form_fields

pytestmark = [pytest.mark.django_db]


@pytest.fixture
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

    assert flex_price_form.form_fields.count() == 4

    field_names = {field.clean_name for field in flex_price_form.form_fields.all()}
    assert field_names == {
        "your_income",
        "income_currency",
        "country_of_income",
        "country_of_residence",
    }


@pytest.mark.parametrize(
    "clean_name",
    ["your_income", "income_currency", "country_of_income", "country_of_residence"],
)
def test_form_with_misnamed_fields(flex_price_form, clean_name):
    """
    Tests a form that has a field with clean_name set right but the label isn't.
    This should still work and the defined field should be left alone.
    """

    assert flex_price_form.form_fields.count() == 0

    # Create a field with a fuzzy label first, then update clean_name after save
    # (because Wagtail's AbstractFormField.save() overwrites clean_name for new fields)
    new_field = FormField(
        page=flex_price_form,
        required=True,
        label=factory.fuzzy.FuzzyText("Form Field "),
    )

    field_types = {
        "your_income": "number",
        "income_currency": "country",
        "country_of_income": "iso_country",
        "country_of_residence": "iso_country",
    }

    new_field.save()

    # Now update clean_name after the initial save
    new_field.clean_name = clean_name
    new_field.field_type = field_types[clean_name]

    new_field.save()
    new_field.refresh_from_db()

    flex_price_form.refresh_from_db()

    assert ensure_flexprice_form_fields(flex_price_form) is False
    assert flex_price_form.form_fields.count() == 4

    for field in flex_price_form.form_fields.all():
        if field == new_field:
            assert field.clean_name == clean_name
            assert new_field.clean_name == clean_name
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

    FormField.objects.create(
        page=flex_price_form,
        clean_name="country_of_income",
        label="Country of Income",
        field_type="iso_country",
        required=True,
    )

    FormField.objects.create(
        page=flex_price_form,
        clean_name="country_of_residence",
        label="Country of Residence",
        field_type="iso_country",
        required=True,
    )

    assert ensure_flexprice_form_fields(flex_price_form) is True
