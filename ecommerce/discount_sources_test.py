from decimal import Decimal

import pytest
import reversion
from django.contrib.auth.models import AnonymousUser

from b2b.factories import ContractPageFactory
from b2b.models import ContractProgramItem
from courses.factories import CourseRunFactory, ProgramFactory
from ecommerce.constants import (
    DISCOUNT_TYPE_PERCENT_OFF,
    REDEMPTION_TYPE_PROGRAM_CHILD_PURCHASE,
)
from ecommerce.discount_sources import (
    double_spent_source_line_ids,
    find_source_conflict,
    released_source_lines,
    resolve_for_discount,
    resolve_program_child_purchase,
    resolved_amounts_for_user,
    resolved_amounts_from_redemptions,
)
from ecommerce.factories import (
    DiscountFactory,
    DiscountRedemptionFactory,
    OrderFactory,
    PaidAmountOffDiscountFactory,
    ProductFactory,
    ProgramProductFactory,
    make_purchase,
)
from ecommerce.models import DiscountProduct, OrderStatus

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def program():
    return ProgramFactory.create()


@pytest.fixture
def program_product(program):
    with reversion.create_revision():
        return ProgramProductFactory.create(purchasable_object=program)


def test_resolves_a_fulfilled_child_course_purchase(user, program, program_product):
    """A paid run of a direct child course funds the discount at what was paid."""
    run = CourseRunFactory.create()
    program.add_requirement(run.course)
    line = make_purchase(user, run, Decimal("100.00"), paid=Decimal("75.00"))

    resolution = resolve_program_child_purchase(user, program_product)

    assert resolution.source_line == line
    assert resolution.amount == Decimal("75.00")


def test_resolves_a_child_program_purchase(user, program, program_product):
    """A purchased vertical (child program) is a valid source."""
    vertical = ProgramFactory.create()
    program.add_requirement(vertical)
    line = make_purchase(user, vertical, Decimal("300.00"))

    assert resolve_program_child_purchase(user, program_product).source_line == line


def test_an_elective_child_course_qualifies(user, program, program_product):
    """Electives are children too: eligibility is one tree level, not one operator."""
    run = CourseRunFactory.create()
    program.add_elective(run.course)
    line = make_purchase(user, run, Decimal("100.00"))

    assert resolve_program_child_purchase(user, program_product).source_line == line


def test_picks_the_most_expensive_qualifying_source(user, program, program_product):
    """The credit is one purchase, the most expensive, not the sum."""
    run_a, run_b = CourseRunFactory.create_batch(2)
    program.add_requirement(run_a.course)
    program.add_requirement(run_b.course)
    make_purchase(user, run_a, Decimal("100.00"))
    best = make_purchase(user, run_b, Decimal("150.00"))

    assert resolve_program_child_purchase(user, program_product).source_line == best


def test_only_fulfilled_source_orders_qualify(user, program, program_product):
    """A refunded (or never-paid) purchase is not a source."""
    run = CourseRunFactory.create()
    program.add_requirement(run.course)
    make_purchase(user, run, Decimal("100.00"), state=OrderStatus.REFUNDED)

    assert resolve_program_child_purchase(user, program_product) is None


def test_equal_prices_break_the_tie_on_the_newest_line(user, program, program_product):
    """Sibling courses often share a price; the choice must be stable, not arbitrary."""
    run_a, run_b = CourseRunFactory.create_batch(2)
    program.add_requirement(run_a.course)
    program.add_requirement(run_b.course)
    make_purchase(user, run_a, Decimal("100.00"))
    newest = make_purchase(user, run_b, Decimal("100.00"))

    assert resolve_program_child_purchase(user, program_product).source_line == newest


def test_a_free_source_credits_nothing(user, program, program_product):
    """A $0 purchase (a 100% code, a free enrollment) is not a source."""
    run = CourseRunFactory.create()
    program.add_requirement(run.course)
    make_purchase(user, run, Decimal("0.00"))

    assert resolve_program_child_purchase(user, program_product) is None


def test_a_consumed_source_does_not_resolve_again(user, program, program_product):
    """A source funds at most one redemption; only FULFILLED consumption counts."""
    run = CourseRunFactory.create()
    program.add_requirement(run.course)
    line = make_purchase(user, run, Decimal("100.00"))
    redemption = DiscountRedemptionFactory.create(
        redeemed_by=user,
        redeemed_discount=PaidAmountOffDiscountFactory.create(),
        redeemed_order=OrderFactory.create(purchaser=user, state=OrderStatus.PENDING),
        source_line=line,
    )
    # An abandoned checkout never burns the source...
    assert resolve_program_child_purchase(user, program_product).source_line == line

    redemption.redeemed_order.state = OrderStatus.FULFILLED
    redemption.redeemed_order.save()

    # ...but a fulfilled one does.
    assert resolve_program_child_purchase(user, program_product) is None


def test_a_standard_discount_never_consumes_a_source(user, program, program_product):
    """Nothing at the DB level keeps source_line off a percent-off redemption, so
    the consumed-source exclusion filters the discount type itself.
    """
    run = CourseRunFactory.create()
    program.add_requirement(run.course)
    line = make_purchase(user, run, Decimal("100.00"))
    DiscountRedemptionFactory.create(
        redeemed_by=user,
        redeemed_discount=DiscountFactory.create(),
        redeemed_order=OrderFactory.create(purchaser=user, state=OrderStatus.FULFILLED),
        source_line=line,
    )

    assert resolve_program_child_purchase(user, program_product).source_line == line


def test_consumption_is_a_single_redemption_row(user, program, program_product):
    """
    A pending paid-amount-off hold and a separate standard redemption on a
    fulfilled order are not, together, a spend: the type and the state must
    hold on the same redemption row.
    """
    run = CourseRunFactory.create()
    program.add_requirement(run.course)
    line = make_purchase(user, run, Decimal("100.00"))
    DiscountRedemptionFactory.create(
        redeemed_by=user,
        redeemed_discount=PaidAmountOffDiscountFactory.create(),
        redeemed_order=OrderFactory.create(purchaser=user, state=OrderStatus.PENDING),
        source_line=line,
    )
    DiscountRedemptionFactory.create(
        redeemed_by=user,
        redeemed_discount=DiscountFactory.create(),
        redeemed_order=OrderFactory.create(purchaser=user, state=OrderStatus.FULFILLED),
        source_line=line,
    )

    assert resolve_program_child_purchase(user, program_product).source_line == line


def test_only_paid_amount_off_eligibility_needs_an_unconsumed_source(
    paid_amount_off_source,
):
    """
    Consumption is a paid-amount-off concept: once a source funds a fulfilled
    paid-amount-off order no paid-amount-off discount resolves it again, but a
    percent-off discount with the program-child-purchase redemption type still
    qualifies on it — that offer takes nothing from the purchase.
    """
    DiscountRedemptionFactory.create(
        redeemed_by=paid_amount_off_source.user,
        redeemed_discount=paid_amount_off_source.discount,
        redeemed_order=OrderFactory.create(
            purchaser=paid_amount_off_source.user, state=OrderStatus.FULFILLED
        ),
        source_line=paid_amount_off_source.source_line,
    )
    percent_off = DiscountFactory.create(
        discount_type=DISCOUNT_TYPE_PERCENT_OFF,
        redemption_type=REDEMPTION_TYPE_PROGRAM_CHILD_PURCHASE,
        automatic=True,
    )
    DiscountProduct.objects.create(
        discount=percent_off, product=paid_amount_off_source.program_product
    )
    products = [paid_amount_off_source.program_product]

    assert (
        resolve_for_discount(
            paid_amount_off_source.discount, paid_amount_off_source.user, products
        )
        is None
    )
    assert (
        resolve_for_discount(
            percent_off, paid_amount_off_source.user, products
        ).source_line
        == paid_amount_off_source.source_line
    )


def test_a_credit_resolves_for_the_first_linked_product(paid_amount_off_source):
    """
    The credit is resolved for the first product the discount is linked to:
    unlinked products ahead of it are skipped, and a linked product ahead of it
    decides the answer even when a later one would have qualified.
    """
    source = paid_amount_off_source
    unlinked_product = ProductFactory.create()
    sourceless_program_product = ProgramProductFactory.create()
    DiscountProduct.objects.create(
        discount=source.discount, product=sourceless_program_product
    )

    assert (
        resolve_for_discount(
            source.discount, source.user, [unlinked_product, source.program_product]
        ).source_line
        == source.source_line
    )
    assert (
        resolve_for_discount(
            source.discount,
            source.user,
            [sourceless_program_product, source.program_product],
        )
        is None
    )


def test_grandchild_courses_do_not_qualify(user, program, program_product):
    """A nested program's courses are rows of its own tree, not of the parent's."""
    vertical = ProgramFactory.create()
    program.add_requirement(vertical)
    run = CourseRunFactory.create()
    vertical.add_requirement(run.course)
    make_purchase(user, run, Decimal("100.00"))

    assert resolve_program_child_purchase(user, program_product) is None


def test_b2b_run_sources_do_not_qualify(user, program, program_product):
    run = CourseRunFactory.create(b2b_contract=ContractPageFactory.create())
    program.add_requirement(run.course)
    make_purchase(user, run, Decimal("100.00"))

    assert resolve_program_child_purchase(user, program_product) is None


def test_b2b_child_program_sources_do_not_qualify(user, program, program_product):
    """A contract-linked vertical is bought under contract terms, not this offer."""
    vertical = ProgramFactory.create()
    ContractProgramItem.objects.create(
        contract=ContractPageFactory.create(), program=vertical
    )
    program.add_requirement(vertical)
    make_purchase(user, vertical, Decimal("300.00"))

    assert resolve_program_child_purchase(user, program_product) is None


def test_non_program_products_do_not_resolve(user):
    run_product = ProductFactory.create()

    assert resolve_program_child_purchase(user, run_product) is None


@pytest.mark.parametrize("field", ["b2b_only", "contract"])
def test_b2b_programs_do_not_resolve(user, field):
    """A B2B program is priced by contract, so it is never offered the credit."""
    program = ProgramFactory.create(b2b_only=field == "b2b_only")
    if field == "contract":
        ContractProgramItem.objects.create(
            contract=ContractPageFactory.create(), program=program
        )
    with reversion.create_revision():
        product = ProgramProductFactory.create(purchasable_object=program)
    run = CourseRunFactory.create()
    program.add_requirement(run.course)
    make_purchase(user, run, Decimal("100.00"))

    assert resolve_program_child_purchase(user, product) is None


def test_anonymous_users_do_not_resolve(program_product):
    assert resolve_program_child_purchase(AnonymousUser(), program_product) is None
    assert resolve_program_child_purchase(None, program_product) is None


def test_resolved_amounts_for_user_keys_by_discount(paid_amount_off_source):
    """Each linked discount resolves over its own links, so a discount that is not
    linked to the product in hand gets no amount rather than the neighbour's.
    """
    unlinked = PaidAmountOffDiscountFactory.create()

    amounts = resolved_amounts_for_user(
        paid_amount_off_source.user,
        [paid_amount_off_source.discount, unlinked],
        [paid_amount_off_source.program_product],
    )

    assert amounts == {paid_amount_off_source.discount.id: Decimal("100.00")}


def test_resolved_amounts_for_user_is_empty_without_paid_amount_off_discounts(
    user, program_product
):
    """A standard discount gets no resolved amount."""
    assert (
        resolved_amounts_for_user(user, [DiscountFactory.create()], [program_product])
        == {}
    )


def test_resolved_amounts_from_redemptions_reads_the_frozen_fk(user):
    """Order paths price from the persisted line, never re-resolving."""
    line = make_purchase(user, CourseRunFactory.create(), Decimal("80.00"))
    discount = PaidAmountOffDiscountFactory.create()
    redemption = DiscountRedemptionFactory.create(
        redeemed_discount=discount, redeemed_by=user, source_line=line
    )
    sourceless = DiscountRedemptionFactory.create(redeemed_by=user)

    amounts = resolved_amounts_from_redemptions([redemption, sourceless])

    assert amounts == {discount.id: Decimal("80.00")}


def test_resolved_amounts_from_redemptions_ignores_standard_discounts(user):
    """The discount type, not the FK, decides who carries a resolved amount."""
    line = make_purchase(user, CourseRunFactory.create(), Decimal("80.00"))
    redemption = DiscountRedemptionFactory.create(
        redeemed_discount=DiscountFactory.create(), redeemed_by=user, source_line=line
    )

    assert resolved_amounts_from_redemptions([redemption]) == {}


def _redemption_on(order, source_line, discount=None):
    return DiscountRedemptionFactory.create(
        redeemed_by=order.purchaser,
        redeemed_discount=discount or PaidAmountOffDiscountFactory.create(),
        redeemed_order=order,
        source_line=source_line,
    )


def test_find_source_conflict_reports_a_fulfilled_competitor(paid_amount_off_source):
    """Another fulfilled order already spent this source: that redemption is the conflict."""
    source_line = paid_amount_off_source.source_line
    order = OrderFactory.create(
        purchaser=paid_amount_off_source.user, state=OrderStatus.FULFILLED
    )
    _redemption_on(order, source_line, paid_amount_off_source.discount)
    competitor = _redemption_on(
        OrderFactory.create(
            purchaser=paid_amount_off_source.user, state=OrderStatus.FULFILLED
        ),
        source_line,
    )
    # A standard redemption on a fulfilled order may carry the same line and is
    # not a competitor.
    _redemption_on(
        OrderFactory.create(
            purchaser=paid_amount_off_source.user, state=OrderStatus.FULFILLED
        ),
        source_line,
        DiscountFactory.create(),
    )

    assert find_source_conflict(order) == competitor


def test_released_source_lines_lists_each_refunded_source_once(
    paid_amount_off_source,
):
    """
    A source whose order was refunded after pricing is reported once, however
    many paid-amount-off redemptions on this order it funds; a standard
    redemption's source_line is not a source at all.
    """
    order = OrderFactory.create(
        purchaser=paid_amount_off_source.user, state=OrderStatus.PENDING
    )
    refunded = paid_amount_off_source.source_line
    refunded.order.state = OrderStatus.REFUNDED
    refunded.order.save()
    _redemption_on(order, refunded)
    _redemption_on(order, refunded)
    standard_source = make_purchase(
        paid_amount_off_source.user,
        CourseRunFactory.create(),
        Decimal("50.00"),
        state=OrderStatus.REFUNDED,
    )
    _redemption_on(order, standard_source, DiscountFactory.create())

    assert list(released_source_lines(order)) == [refunded]


def test_find_source_conflict_ignores_a_pending_competitor(paid_amount_off_source):
    """An abandoned checkout holding the same source is not a double spend."""
    order = OrderFactory.create(
        purchaser=paid_amount_off_source.user, state=OrderStatus.PENDING
    )
    DiscountRedemptionFactory.create(
        redeemed_by=paid_amount_off_source.user,
        redeemed_discount=paid_amount_off_source.discount,
        redeemed_order=order,
        source_line=paid_amount_off_source.source_line,
    )
    competitor = OrderFactory.create(
        purchaser=paid_amount_off_source.user, state=OrderStatus.PENDING
    )
    DiscountRedemptionFactory.create(
        redeemed_by=paid_amount_off_source.user,
        redeemed_discount=PaidAmountOffDiscountFactory.create(),
        redeemed_order=competitor,
        source_line=paid_amount_off_source.source_line,
    )

    assert find_source_conflict(order) is None


def test_find_source_conflict_ignores_the_orders_own_redemption(paid_amount_off_source):
    """The order being fulfilled always holds the source itself — that is not a
    conflict, and this is the case the check runs against on every fulfillment.
    """
    order = OrderFactory.create(
        purchaser=paid_amount_off_source.user, state=OrderStatus.FULFILLED
    )
    DiscountRedemptionFactory.create(
        redeemed_by=paid_amount_off_source.user,
        redeemed_discount=paid_amount_off_source.discount,
        redeemed_order=order,
        source_line=paid_amount_off_source.source_line,
    )

    assert find_source_conflict(order) is None


def test_double_spent_source_line_ids_ignores_standard_redemptions(
    paid_amount_off_source,
):
    """A standard redemption may legally carry a source_line, but only a
    paid-amount-off redemption spends one, so the pair is not a double spend.
    """
    source_line = paid_amount_off_source.source_line
    for discount in (PaidAmountOffDiscountFactory.create(), DiscountFactory.create()):
        DiscountRedemptionFactory.create(
            redeemed_by=paid_amount_off_source.user,
            redeemed_discount=discount,
            redeemed_order=OrderFactory.create(state=OrderStatus.FULFILLED),
            source_line=source_line,
        )

    assert double_spent_source_line_ids() == []


def test_double_spent_source_line_ids_counts_orders_not_rows(paid_amount_off_source):
    """Two redemptions on one fulfilled order are a re-priced order, not two spends."""
    order = OrderFactory.create(state=OrderStatus.FULFILLED)
    for _ in range(2):
        DiscountRedemptionFactory.create(
            redeemed_by=paid_amount_off_source.user,
            redeemed_discount=PaidAmountOffDiscountFactory.create(),
            redeemed_order=order,
            source_line=paid_amount_off_source.source_line,
        )

    assert double_spent_source_line_ids() == []
