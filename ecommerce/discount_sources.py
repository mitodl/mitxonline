"""
Source resolution for program-child-purchase redemptions (hq#11846, "complete
your program"): a learner who already paid for a course or sub-program in a
program's own requirement tree qualifies, and a paid-amount-off discount takes
what they paid off the program purchase. The redemption type decides
eligibility; only the paid-amount-off discount type gets a resolved amount, a
persisted source line, and consumes its source.

This module owns eligibility and value. The calculation layer
(ecommerce/discounts.py) stays user-blind and receives the resolved amount
via DiscountType.get_discounted_price(..., resolved_amounts=...). Order paths
never re-resolve: PendingOrder persists the winning line on
DiscountRedemption.source_line and resolved_amounts_from_redemptions reads it
back.

Sources are read from Line + Order.state directly, not PaidCourseRun /
PaidProgram: those rows are deleted on learner self-unenroll and skipped by
fulfill(skip_fulfillment=True), while the fulfilled order and line remain.

Two things about the module's shape. It imports ecommerce.models at module
level, so the model layer reaches it through function-local imports (the same
arrangement ecommerce.discounts has); the orchestration that would let the
models stop calling it lives in ecommerce.api and is not moved here. And the
second half of the module is not eligibility or value at all but ledger
queries over persisted redemptions (source conflicts, released sources,
funded credits, double spends); they share the source-line vocabulary and the
paid-amount-off filter, which is why they are colocated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal  # noqa: TC003

from django.contrib.contenttypes.models import ContentType
from django.db.models import (
    Count,
    Exists,
    OuterRef,
    Q,
    QuerySet,
    prefetch_related_objects,
)

from courses.models import (
    CourseRun,
    Program,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from ecommerce.constants import DISCOUNT_TYPE_PAID_AMOUNT_OFF
from ecommerce.models import DiscountRedemption, Line, OrderStatus

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceResolution:
    """The single prior purchase that qualifies a program-child-purchase redemption."""

    source_line: Line
    amount: Decimal


def spends_source(discount) -> bool:
    """
    Whether ``discount`` is funded by, and consumes, a specific source line.

    Only a paid-amount-off discount does; a program-child-purchase redemption
    on any other discount type is eligibility-only and records no source. The
    fulfilled-redemptions queryset below is the ORM spelling of the same rule.
    """
    return discount.discount_type == DISCOUNT_TYPE_PAID_AMOUNT_OFF


def fulfilled_paid_amount_off_redemptions() -> QuerySet[DiscountRedemption]:
    """
    Every FULFILLED redemption of a paid-amount-off discount.

    The discount type is filtered here rather than trusted from the FK: tying
    source_line to the discount type would need a constraint spanning Discount
    and DiscountRedemption, which Postgres cannot express, so a standard
    redemption carrying a source_line is legal at the DB level.
    """
    return DiscountRedemption.objects.filter(
        redeemed_discount__discount_type=DISCOUNT_TYPE_PAID_AMOUNT_OFF,
        redeemed_order__state=OrderStatus.FULFILLED,
    )


def _program_for_product(product) -> Program | None:
    """The program ``product`` sells, if it is an eligible current purchase."""
    program = product.purchasable_object
    if not isinstance(program, Program):
        return None
    # B2B programs are priced by contract, not by this offer. b2b_only alone
    # is incomplete: contract-linked programs are not required to set it.
    if program.b2b_only or program.contract_memberships.exists():
        return None
    return program


def resolve_program_child_purchase(
    user, product, *, exclude_consumed=True
) -> SourceResolution | None:
    """
    The most expensive unconsumed qualifying purchase of a course or
    sub-program in ``product``'s program's own requirement tree, or None.

    Qualifying: a Line on one of the user's FULFILLED orders whose purchased
    run or program is not B2B, for a run of a course in the tree or for a
    sub-program in the tree, at any depth but not through a nested program's
    own tree, with a recorded price above zero. Consumed: the
    line already funds a paid-amount-off redemption on a FULFILLED order
    (pending/abandoned checkouts never burn a source). Only a paid-amount-off
    discount spends its source, so resolve_for_discount passes
    exclude_consumed=False for any other discount type with the
    program-child-purchase redemption.
    """
    if user is None or user.is_anonymous:
        return None
    program = _program_for_product(product)
    if program is None:
        return None

    # Every row of this program's requirement tree carries this program's FK,
    # whatever its depth, so this matches a course or sub-program anywhere in
    # the tree. A nested program's own courses are rows of that program's tree
    # and never match. Both queries span required and elective children, because
    # the operator node they hang off is the parent, not the row matched here.
    #
    # Program.courses and Program.program_nodes are the equivalent accessors;
    # the ids are queried directly instead because nothing here needs hydrated
    # objects, and values_list keeps the whole thing a subquery the source-line
    # filter can join against.
    child_course_ids = ProgramRequirement.objects.filter(
        program=program,
        node_type=ProgramRequirementNodeType.COURSE,
        course__isnull=False,
    ).values_list("course_id", flat=True)
    child_program_ids = ProgramRequirement.objects.filter(
        program=program,
        node_type=ProgramRequirementNodeType.PROGRAM,
        required_program__isnull=False,
    ).values_list("required_program_id", flat=True)

    # B2B purchases never fund the offer.
    source_run_ids = CourseRun.objects.filter(
        course_id__in=child_course_ids, b2b_contract__isnull=True
    ).values_list("id", flat=True)
    source_program_ids = Program.objects.filter(
        id__in=child_program_ids, contract_memberships__isnull=True
    ).values_list("id", flat=True)

    run_ct = ContentType.objects.get_for_model(CourseRun)
    program_ct = ContentType.objects.get_for_model(Program)

    candidates = Line.objects.filter(
        order__purchaser=user,
        order__state=OrderStatus.FULFILLED,
        # discounted_unit_price is the price frozen when the source order
        # was priced (non-null); a $0 purchase has nothing to credit.
        discounted_unit_price__gt=0,
    ).filter(
        Q(purchased_content_type=run_ct, purchased_object_id__in=source_run_ids)
        | Q(
            purchased_content_type=program_ct,
            purchased_object_id__in=source_program_ids,
        )
    )
    if exclude_consumed:
        # A multi-condition exclude() over funded_redemptions compiles to one
        # EXISTS per condition, so the type and the state would be checked on
        # different redemption rows (Django docs, "Spanning multi-valued
        # relationships"). A correlated subquery holds both on the same row.
        candidates = candidates.exclude(
            Exists(
                fulfilled_paid_amount_off_redemptions().filter(
                    source_line=OuterRef("pk")
                )
            )
        )
    # Sibling courses often share a price; the id tie-break keeps the choice
    # stable across the eligibility and pricing resolves of one request.
    source_line = candidates.order_by("-discounted_unit_price", "-id").first()
    if source_line is None:
        return None
    return SourceResolution(
        source_line=source_line,
        amount=source_line.get_discounted_unit_price(),
    )


def resolve_for_discount(discount, user, products) -> SourceResolution | None:
    """
    Resolve for the first of ``products`` that ``discount`` is linked to, or
    None when it is linked to none of them.

    The eligibility guard, the basket display and order creation all resolve
    through here, so a discount cannot validate against one line and price
    another. A program-child-purchase discount names its programs through its
    links, so an unlinked one has nothing to resolve for.

    The pricing sites apply a discount to every line, so a multi-item basket
    that holds more than one linked program gets this one resolution on each
    of them; hq#12815 narrows pricing to the same single product.
    """
    # Several discounts resolve in one request, and a lazy read of the links per
    # discount trips the N+1 guard (zeal); an explicit prefetch does not.
    prefetch_related_objects([discount], "products")
    linked_product_ids = {link.product_id for link in discount.products.all()}
    product = next(
        (product for product in products if product.id in linked_product_ids), None
    )
    if product is None:
        return None
    return resolve_program_child_purchase(
        user, product, exclude_consumed=spends_source(discount)
    )


def source_line_for(discount, user, products) -> Line | None:
    """
    The prior purchase line that funds ``discount`` for ``user``, to persist on
    the redemption at order creation; None for a discount that spends no
    source. Resolving for the same target product the eligibility guard uses
    keeps the persisted source from disagreeing with is_redeemable_by.
    """
    if not spends_source(discount):
        return None
    resolution = resolve_for_discount(discount, user, products)
    return resolution.source_line if resolution else None


def has_paid_amount_off(discounts) -> bool:
    """Whether any of ``discounts`` spends a source, i.e. needs resolving."""
    return any(spends_source(discount) for discount in discounts)


def resolved_amounts_for_user(user, discounts, products) -> dict[int, Decimal]:
    """
    {discount_id: amount} for the paid-amount-off discounts in ``discounts``.

    Each discount resolves for its own target line, so two paid-amount-off
    discounts covering different programs in one basket get different answers. For
    user/basket pricing paths; order paths must use
    resolved_amounts_from_redemptions so the price stays frozen.
    """
    resolutions = {
        discount.id: resolve_for_discount(discount, user, products)
        for discount in discounts
        if spends_source(discount)
    }
    return {
        discount_id: resolution.amount
        for discount_id, resolution in resolutions.items()
        if resolution is not None
    }


def resolved_amounts_from_redemptions(redemptions) -> dict[int, Decimal]:
    """
    {discount_id: amount} read back from persisted source_line FKs — zero
    resolver queries, frozen at order creation.

    Callers should select_related("redeemed_discount", "source_line"):
    redeemed_discount is read on every row, source_line on the paid-amount-off
    rows.

    Keying on source_line_id alone would be wrong: a standard redemption may
    legally carry one, and DiscountType.for_discount raises TypeError when a
    resolved amount reaches a discount type that has no field for it.
    """
    return {
        redemption.redeemed_discount_id: redemption.source_line.get_discounted_unit_price()
        for redemption in redemptions
        if redemption.source_line_id is not None
        and spends_source(redemption.redeemed_discount)
    }


def paid_amount_off_source_line_ids(order) -> list[int]:
    """Ids of the source lines ``order``'s paid-amount-off redemptions were priced from."""
    return [
        redemption.source_line_id
        for redemption in order.discounts.select_related("redeemed_discount")
        if redemption.source_line_id is not None
        and spends_source(redemption.redeemed_discount)
    ]


def find_source_conflict(order, source_line_ids=None) -> DiscountRedemption | None:
    """
    A FULFILLED redemption on another order that already consumed one of the
    source lines ``order`` was priced from, or None.

    Called at fulfillment time: nothing re-validates between pricing and
    payment, so one source line can otherwise deterministically fund two
    different program purchases. ``source_line_ids`` is
    paid_amount_off_source_line_ids(order), for a caller that already has it.
    """
    if source_line_ids is None:
        source_line_ids = paid_amount_off_source_line_ids(order)
    if not source_line_ids:
        return None
    return (
        fulfilled_paid_amount_off_redemptions()
        .filter(source_line_id__in=source_line_ids)
        .exclude(redeemed_order=order)
        .select_related("redeemed_order")
        .first()
    )


def released_source_lines(order) -> QuerySet[Line]:
    """
    The source lines ``order`` was priced from whose own order is no longer
    FULFILLED — refunded between pricing and payment, so the credit baked into
    this order's price rests on a purchase the learner no longer holds.
    """
    return (
        Line.objects.filter(
            funded_redemptions__redeemed_order=order,
            funded_redemptions__redeemed_discount__discount_type=DISCOUNT_TYPE_PAID_AMOUNT_OFF,
        )
        .exclude(order__state=OrderStatus.FULFILLED)
        .select_related("order")
        .distinct()
    )


def log_source_anomalies(order) -> None:
    """
    At fulfillment, log the two states the double-spend window can leave
    ``order`` in: a source line another FULFILLED order already spent, or a
    source line whose own order was refunded between pricing and payment.

    Nothing re-validates between pricing and payment, and the single-cart
    checkout makes either state rare, so the credit is honored and the error is
    made Sentry-visible for a manual refund rather than blocking a payment that
    already went through. Each message names both orders and the source line.
    """
    source_line_ids = paid_amount_off_source_line_ids(order)
    if not source_line_ids:
        return
    conflict = find_source_conflict(order, source_line_ids)
    if conflict is not None:
        log.error(
            "Order %s fulfilled with paid-amount-off source line %s that "
            "already funds fulfilled order %s — double credit honored; "
            "review manually.",
            order.reference_number,
            conflict.source_line_id,
            conflict.redeemed_order.reference_number,
        )
    for line in released_source_lines(order):
        log.error(
            "Order %s fulfilled with paid-amount-off source line %s whose "
            "own order %s is no longer fulfilled — credit rests on a "
            "purchase the learner no longer holds; review manually.",
            order.reference_number,
            line.id,
            line.order.reference_number,
        )


def fulfilled_redemptions_funded_by(order) -> QuerySet[DiscountRedemption]:
    """
    FULFILLED paid-amount-off redemptions on other orders that a line of
    ``order`` funded — the credits that survive refunding ``order``, since
    OrderFlow.refund touches only transactions.
    """
    return (
        fulfilled_paid_amount_off_redemptions()
        .filter(source_line__order=order)
        .exclude(redeemed_order=order)
        # Callers that read rows name the order the credit went to; an
        # exists() caller pays nothing for the join.
        .select_related("redeemed_order")
    )


def double_spent_source_line_ids() -> list[int]:
    """
    Source lines funding a FULFILLED paid-amount-off redemption on more than one
    order — the state the fulfillment-time check logs and honors.

    Counted over distinct orders, not rows: two paid-amount-off discounts on
    one order resolving the same line are two rows but one spend.
    """
    return list(
        fulfilled_paid_amount_off_redemptions()
        .filter(source_line__isnull=False)
        .values("source_line")
        .annotate(order_count=Count("redeemed_order", distinct=True))
        .filter(order_count__gt=1)
        .values_list("source_line", flat=True)
    )
