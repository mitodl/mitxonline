"""Tests for tax calculation."""

from decimal import Decimal

import pytest
import reversion
from django.contrib.admin.sites import AdminSite
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from reversion.models import Version

from courses.factories import CourseRunFactory, ProgramFactory
from ecommerce.admin import TaxRateAdmin
from ecommerce.factories import ProductFactory, TaxRateFactory
from ecommerce.models import Product, TaxRate
from ecommerce.tax import (
    TaxRateVersionError,
    calculate_tax,
    calculate_tax_for_locale,
    calculate_tax_for_product,
    get_product,
    get_tax_rate_for_locale,
)
from users.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("amount", "rate", "expected_tax"),
    [
        (Decimal("100.00"), Decimal(18), Decimal("18.00")),
        (Decimal("49.99"), Decimal("12.5"), Decimal("6.25")),  # 6.24875 rounds up
        (Decimal("10.00"), Decimal("0.0500"), Decimal("0.01")),  # 0.005 rounds up
        (Decimal("10.00"), Decimal("0.0400"), Decimal("0.00")),
        (Decimal("10.00"), Decimal(0), Decimal("0.00")),
    ],
)
def test_calculate_tax(amount, rate, expected_tax):
    """calculate_tax applies the rate and rounds the tax half-up to the cent."""

    tax_rate = TaxRateFactory.create(country_code="IN", tax_rate=rate)

    result = calculate_tax(amount, tax_rate)

    assert result.tax_rate == tax_rate
    assert result.rate == rate
    assert result.taxable_amount == amount
    assert result.tax_amount == expected_tax
    assert result.total == amount + expected_tax
    assert result.tax_rate_name == tax_rate.tax_rate_name
    assert result.is_taxed is True
    assert result.tax_rate_version == tax_rate.current_version


def test_calculate_tax_uses_saved_rate():
    """A stale rate is re-read, so the rate applied matches the version returned."""

    stale = TaxRateFactory.create(country_code="IN", tax_rate=Decimal(18))
    fresh = TaxRate.objects.get(pk=stale.pk)
    fresh.tax_rate = Decimal(20)
    fresh.save()

    result = calculate_tax(Decimal("100.00"), stale)

    assert result.rate == Decimal(20)
    assert result.tax_amount == Decimal("20.00")
    assert result.tax_rate_version == fresh.current_version
    assert Decimal(result.tax_rate_version.field_dict["tax_rate"]) == result.rate


def test_calculate_tax_in_open_revision():
    """A rate whose version isn't saved yet can't be used, so no wrong version is pinned."""

    tax_rate = TaxRateFactory.create(country_code="IN", tax_rate=Decimal(18))

    with reversion.create_revision():
        tax_rate.tax_rate = Decimal(20)
        tax_rate.save()

        with pytest.raises(TaxRateVersionError):
            calculate_tax(Decimal("100.00"), tax_rate)

    assert calculate_tax(Decimal("100.00"), tax_rate).rate == Decimal(20)


def test_calculate_tax_new_rate_in_open_revision():
    """A rate created in an open revision has no version yet, so it can't be used."""

    with reversion.create_revision():
        tax_rate = TaxRateFactory.create(country_code="IN")

        with pytest.raises(TaxRateVersionError):
            calculate_tax(Decimal("100.00"), tax_rate)


@pytest.mark.parametrize("amount", [Decimal("100.00"), Decimal(0)])
def test_calculate_tax_no_rate(amount):
    """Without a rate there is no tax, and the total is the amount."""

    result = calculate_tax(amount, None)

    assert result.tax_rate is None
    assert result.tax_rate_version is None
    assert result.rate == 0
    assert result.tax_amount == 0
    assert result.total == amount
    assert result.tax_rate_name == ""
    assert result.is_taxed is False


@pytest.mark.parametrize("amount", [Decimal(0), Decimal("-5.00")])
def test_calculate_tax_zero_amount(amount):
    """A free item in a taxed locale owes no tax, but still records the rate."""

    tax_rate = TaxRateFactory.create(country_code="IN")

    result = calculate_tax(amount, tax_rate)

    assert result.tax_rate == tax_rate
    assert result.tax_amount == 0
    assert result.total == amount
    assert result.is_taxed is True


def test_calculate_tax_float_amount():
    """A float amount doesn't carry its binary error into the result."""

    tax_rate = TaxRateFactory.create(country_code="IN", tax_rate=Decimal(10))

    result = calculate_tax(19.99, tax_rate)

    assert result.taxable_amount == Decimal("19.99")
    assert result.total == Decimal("21.99")


@pytest.mark.parametrize("country_code", ["IN", "in"])
def test_get_tax_rate_for_locale(country_code):
    """The active country-level rate is found, whatever the code's case."""

    tax_rate = TaxRateFactory.create(country_code="IN")
    TaxRateFactory.create(country_code="GB")

    assert get_tax_rate_for_locale(country_code) == tax_rate


@pytest.mark.parametrize("country_code", [None, "", "US"])
def test_get_tax_rate_for_locale_none(country_code):
    """No rate is returned for an unknown or untaxed locale."""

    TaxRateFactory.create(country_code="IN")

    assert get_tax_rate_for_locale(country_code) is None


def test_get_tax_rate_for_locale_skips_inactive_and_subdivisions():
    """Deleted rates and subdivision rates are not matched."""

    TaxRateFactory.create(country_code="IN").delete()
    TaxRateFactory.create(country_code="IN", subdivision_1_code="KA")

    assert get_tax_rate_for_locale("IN") is None

    active = TaxRateFactory.create(country_code="IN")

    assert get_tax_rate_for_locale("IN") == active


def test_tax_rate_unique_active_locale():
    """Only one active rate may exist for a locale, but deleted ones don't count.

    The factory's create() skips full_clean (force_insert), so save() is used.
    """

    first = TaxRateFactory.create(country_code="IN")

    with pytest.raises(ValidationError):
        TaxRateFactory.build(country_code="IN").save()

    first.delete()

    assert TaxRate.all_objects.filter(pk=first.pk, is_active=False).exists()
    TaxRateFactory.create(country_code="IN")


@pytest.mark.parametrize("rate", [Decimal(-1), Decimal(100), Decimal("150.5")])
def test_tax_rate_unbounded(rate):
    """The rate isn't bounded, so an unusual rate can still be stored as set."""

    tax_rate = TaxRateFactory.build(country_code="IN", tax_rate=rate)
    tax_rate.save()

    tax_rate.refresh_from_db()
    assert tax_rate.tax_rate == rate


@pytest.mark.parametrize("in_revision", [True, False])
def test_tax_rate_is_versioned(in_revision):
    """Every change to a rate records a version, inside a revision or not."""

    tax_rate = TaxRateFactory.create(country_code="IN", tax_rate=Decimal(18))

    tax_rate.tax_rate = Decimal(20)
    if in_revision:
        with reversion.create_revision():
            tax_rate.save()
    else:
        tax_rate.save()

    versions = Version.objects.get_for_object(tax_rate)

    assert [Decimal(v.field_dict["tax_rate"]) for v in versions] == [
        Decimal(20),
        Decimal(18),
    ]
    assert tax_rate.current_version == versions.first()


def test_tax_rate_delete_is_versioned():
    """Deleting a rate records a version showing it inactive."""

    tax_rate = TaxRateFactory.create(country_code="IN")

    tax_rate.delete()

    assert tax_rate.current_version.field_dict["is_active"] is False


def test_tax_rate_delete_versions_saved_rate():
    """A deletion's version records the rate as saved, not a stale copy of it."""

    stale = TaxRateFactory.create(country_code="IN", tax_rate=Decimal(18))
    fresh = TaxRate.objects.get(pk=stale.pk)
    fresh.tax_rate = Decimal(20)
    fresh.save()

    stale.delete()

    assert Decimal(stale.current_version.field_dict["tax_rate"]) == Decimal(20)
    assert stale.current_version.field_dict["is_active"] is False
    assert stale.tax_rate == Decimal(20)


def test_tax_rate_admin_bulk_delete_is_versioned():
    """The admin's bulk delete versions each deletion."""

    rates = [
        TaxRateFactory.create(country_code="IN"),
        TaxRateFactory.create(country_code="GB"),
    ]

    request = RequestFactory().post("/")
    request.user = UserFactory.create()

    TaxRateAdmin(TaxRate, AdminSite()).delete_queryset(
        request, TaxRate.objects.filter(pk__in=[rate.pk for rate in rates])
    )

    for rate in rates:
        rate.refresh_from_db()
        assert rate.is_active is False
        assert rate.current_version.field_dict["is_active"] is False
        assert rate.current_version.revision.user == request.user


def test_tax_rate_admin_bulk_delete_skips_deleted():
    """The admin's bulk delete leaves already-deleted rates alone."""

    rate = TaxRateFactory.create(country_code="IN")
    rate.delete()
    rate.refresh_from_db()
    deleted_on = rate.deleted_on
    version_count = Version.objects.get_for_object(rate).count()

    request = RequestFactory().post("/")
    request.user = UserFactory.create()

    TaxRateAdmin(TaxRate, AdminSite()).delete_queryset(
        request, TaxRate.all_objects.filter(pk=rate.pk)
    )

    rate.refresh_from_db()
    assert rate.deleted_on == deleted_on
    assert Version.objects.get_for_object(rate).count() == version_count


@pytest.mark.parametrize("taxed", [True, False])
@pytest.mark.parametrize("price", [None, Decimal("50.00")])
def test_product_calculate_tax_for_locale(taxed, price):
    """Product.calculate_tax_for_locale taxes the product's price, or the given one."""

    product = ProductFactory.create(price=Decimal("200.00"))
    tax_rate = TaxRateFactory.create(country_code="IN", tax_rate=Decimal(10))

    result = product.calculate_tax_for_locale("IN" if taxed else "US", price=price)

    expected_amount = price if price is not None else product.price
    assert result.taxable_amount == expected_amount
    if taxed:
        assert result.tax_rate == tax_rate
        assert result.tax_amount == expected_amount / 10
    else:
        assert result.tax_rate is None
        assert result.tax_amount == 0


@pytest.mark.parametrize("country_code", ["IN", "in"])
def test_calculate_tax_for_locale(country_code):
    """calculate_tax_for_locale taxes at the locale's active rate and pins its version."""

    tax_rate = TaxRateFactory.create(country_code="IN", tax_rate=Decimal(10))

    result = calculate_tax_for_locale(Decimal("50.00"), country_code)

    assert result.tax_rate == tax_rate
    assert result.tax_amount == Decimal("5.00")
    assert result.tax_rate_version == tax_rate.current_version


def test_calculate_tax_for_locale_one_statement(django_assert_num_queries):
    """
    The locale's rate and its version ID come from one statement, so they share
    a snapshot; the version is then loaded by ID. Nothing is locked.
    """

    tax_rate = TaxRateFactory.create(country_code="IN")
    ContentType.objects.get_for_model(TaxRate)  # warm the content type cache

    with django_assert_num_queries(2) as ctx:
        result = calculate_tax_for_locale(Decimal("50.00"), "IN")

    assert result.tax_rate_version == tax_rate.current_version
    assert not any("FOR UPDATE" in query["sql"] for query in ctx.captured_queries)


def test_calculate_tax_for_locale_untaxed():
    """A locale with no active rate owes no tax."""

    TaxRateFactory.create(country_code="IN").delete()

    result = calculate_tax_for_locale(Decimal("50.00"), "IN")

    assert result.is_taxed is False
    assert result.total == Decimal("50.00")


def test_get_product():
    """A product is found by ID, or by its course run's or program's readable ID."""

    run_product = ProductFactory.create()
    program_product = ProductFactory.create(purchasable_object=ProgramFactory.create())

    assert get_product(run_product.id) == run_product
    assert get_product(str(run_product.id)) == run_product
    assert get_product(run_product.purchasable_object.courseware_id) == run_product
    assert (
        get_product(program_product.purchasable_object.readable_id) == program_product
    )

    with pytest.raises(Product.DoesNotExist):
        get_product("course-v1:MITx+nope+1T2099")


def test_get_product_source_run():
    """A product for a source run is found by its readable ID, as by its ID."""

    product = ProductFactory.create(
        purchasable_object=CourseRunFactory.create(is_source_run=True)
    )

    assert get_product(product.purchasable_object.courseware_id) == product


def test_get_product_skips_inactive():
    """An inactive product is not found."""

    product = ProductFactory.create(is_active=False)

    with pytest.raises(Product.DoesNotExist):
        get_product(product.id)


def test_calculate_tax_for_product():
    """calculate_tax_for_product looks the product up and taxes it."""

    product = ProductFactory.create(price=Decimal("100.00"))
    TaxRateFactory.create(country_code="IN", tax_rate=Decimal(18))

    result = calculate_tax_for_product(product.id, "IN")

    assert result.tax_amount == Decimal("18.00")
    assert result.total == Decimal("118.00")
