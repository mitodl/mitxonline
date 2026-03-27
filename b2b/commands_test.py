"""Tests for B2B management commands."""

import pytest
from django.core.management import call_command

from b2b.factories import ContractPageFactory
from b2b.models import DiscountContractAttachmentRedemption
from courses.factories import CourseRunEnrollmentFactory, CourseRunFactory
from ecommerce.factories import (
    DiscountFactory,
    DiscountRedemptionFactory,
    ProductFactory,
)
from ecommerce.models import Discount, DiscountProduct

pytestmark = [pytest.mark.django_db]


def _create_run_with_product_and_discount(contract, *, with_enrollment=False):
    """Helper to create a B2B run, product, discount, and optional enrollment."""

    run = CourseRunFactory.create(b2b_contract=contract, live=True, enrollment_end=None)
    product = ProductFactory.create(purchasable_object=run, is_active=True)
    discount = DiscountFactory.create()
    DiscountProduct.objects.create(discount=discount, product=product)

    if with_enrollment:
        CourseRunEnrollmentFactory.create(run=run)

    return run, product, discount


def test_b2b_courseware_remove_run_without_enrollments_unlinks_and_deactivates(mocker):
    """Removing a run with no enrollments should unlink it and deactivate related objects."""

    mocker.patch("b2b.management.commands.b2b_courseware.update_edx_course")

    contract = ContractPageFactory.create()
    run, product, discount = _create_run_with_product_and_discount(
        contract, with_enrollment=False
    )

    # Sanity checks
    assert run.b2b_contract == contract
    assert product.is_active is True
    assert DiscountProduct.objects.filter(product=product).exists()
    assert Discount.objects.filter(id=discount.id).exists()

    call_command("b2b_courseware", "remove", str(contract.id), run.courseware_id)

    run.refresh_from_db()
    product.refresh_from_db()

    # Run should be deactivated and unlinked
    assert run.live is False
    assert run.enrollment_end is not None
    assert run.b2b_contract is None

    # Product should be deactivated
    assert product.is_active is False

    # Enrollment codes for this run should have been removed
    assert not DiscountProduct.objects.filter(product=product).exists()
    assert not Discount.objects.filter(id=discount.id).exists()


def test_b2b_courseware_remove_run_with_enrollments_keeps_contract_and_deactivates(
    mocker,
):
    """Removing a run with enrollments should keep contract link but deactivate run/products/codes."""

    mocker.patch("b2b.management.commands.b2b_courseware.update_edx_course")

    contract = ContractPageFactory.create()
    run, product, discount = _create_run_with_product_and_discount(
        contract, with_enrollment=True
    )

    # Sanity checks
    assert run.b2b_contract == contract
    assert product.is_active is True
    assert DiscountProduct.objects.filter(product=product).exists()
    assert Discount.objects.filter(id=discount.id).exists()

    call_command("b2b_courseware", "remove", str(contract.id), run.courseware_id)

    run.refresh_from_db()
    product.refresh_from_db()

    # Run should be deactivated but still linked to the contract
    assert run.live is False
    assert run.enrollment_end is not None
    assert run.b2b_contract == contract

    # Product should be deactivated
    assert product.is_active is False

    # Enrollment codes for this run should have been removed
    assert not DiscountProduct.objects.filter(product=product).exists()
    assert not Discount.objects.filter(id=discount.id).exists()


def test_b2b_courseware_remove_run_does_not_delete_used_discount_order_redemption(
    mocker,
):
    """Discounts that have been used for an order should not be deleted."""

    mocker.patch("b2b.management.commands.b2b_courseware.update_edx_course")

    contract = ContractPageFactory.create()
    run, product, discount = _create_run_with_product_and_discount(
        contract, with_enrollment=False
    )

    DiscountRedemptionFactory.create(redeemed_discount=discount)

    call_command("b2b_courseware", "remove", str(contract.id), run.courseware_id)

    assert not DiscountProduct.objects.filter(
        product=product, discount=discount
    ).exists()

    assert Discount.objects.filter(id=discount.id).exists()


def test_b2b_courseware_remove_run_does_not_delete_used_discount_contract_attachment(
    mocker,
):
    """Discounts that have been used to attach a user to a contract should not be deleted."""

    mocker.patch("b2b.management.commands.b2b_courseware.update_edx_course")

    contract = ContractPageFactory.create()
    run, product, discount = _create_run_with_product_and_discount(
        contract, with_enrollment=False
    )

    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        user=contract.organization.get_learners().first()
        or contract.organization.get_learners().model.objects.create(),
        contract=contract,
    )

    call_command("b2b_courseware", "remove", str(contract.id), run.courseware_id)

    assert not DiscountProduct.objects.filter(
        product=product, discount=discount
    ).exists()

    assert Discount.objects.filter(id=discount.id).exists()
