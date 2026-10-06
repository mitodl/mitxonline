"""
Link existing B2B enrollment codes to the contract they belong to.

Until now a code's contract was inferred from the course run its product is
for. A run that belongs to one contract gives one answer. For a run shared by
several contracts, the code goes to the contract it was assigned or redeemed
for, and failing that to the run's original contract (the deprecated
``CourseRun.b2b_contract``). A code that still has more than one candidate is
left unlinked, which takes it out of every contract's pool.
"""

import logging
from collections import defaultdict

from django.db import migrations

log = logging.getLogger(__name__)

UPDATE_BATCH_SIZE = 5000


def _pick_contract(candidates, redeemed_for, original):
    """Return the one contract the code belongs to, or None if it's ambiguous."""

    for narrowed in (candidates, candidates & redeemed_for, candidates & original):
        if len(narrowed) == 1:
            return next(iter(narrowed))

    return None


def _contracts_by_run(CourseRun):
    """Return each run's contracts, and each run's original contract."""

    original_contract = dict(
        CourseRun.all_objects.filter(b2b_contract__isnull=False).values_list(
            "id", "b2b_contract_id"
        )
    )
    run_contracts = defaultdict(set)
    for run_id, contract_id in original_contract.items():
        run_contracts[run_id].add(contract_id)
    for run_id, contract_id in CourseRun.b2b_contracts.through.objects.values_list(
        "courserun_id", "contractpage_id"
    ):
        run_contracts[run_id].add(contract_id)

    return run_contracts, original_contract


def backfill_discount_contracts(apps, schema_editor):
    """Set Discount.b2b_contract for existing enrollment codes."""

    ContentType = apps.get_model("contenttypes", "ContentType")
    CourseRun = apps.get_model("courses", "CourseRun")
    Discount = apps.get_model("ecommerce", "Discount")
    DiscountProduct = apps.get_model("ecommerce", "DiscountProduct")
    Redemption = apps.get_model("b2b", "DiscountContractAttachmentRedemption")

    run_content_type = ContentType.objects.filter(
        app_label="courses", model="courserun"
    ).first()
    if run_content_type is None:
        return

    run_contracts, original_contract = _contracts_by_run(CourseRun)

    # The shape b2b.api._get_discount_defaults gives every enrollment code, so
    # another kind of discount on a run that is also sold publicly is skipped.
    discount_runs = defaultdict(set)
    for discount_id, run_id in DiscountProduct.objects.filter(
        discount__is_bulk=True,
        discount__discount_type="fixed-price",
        discount__payment_type="sales",
        discount__b2b_contract__isnull=True,
        product__content_type=run_content_type,
        product__object_id__in=list(run_contracts),
    ).values_list("discount_id", "product__object_id"):
        discount_runs[discount_id].add(run_id)

    redeemed_for = defaultdict(set)
    for discount_id, contract_id in Redemption.objects.values_list(
        "discount_id", "contract_id"
    ):
        redeemed_for[discount_id].add(contract_id)

    contract_discounts = defaultdict(list)
    ambiguous = []
    for discount_id, run_ids in discount_runs.items():
        contract_id = _pick_contract(
            set().union(*(run_contracts[run_id] for run_id in run_ids)),
            redeemed_for[discount_id],
            {
                original_contract[run_id]
                for run_id in run_ids
                if run_id in original_contract
            },
        )
        if contract_id is None:
            ambiguous.append(discount_id)
        else:
            contract_discounts[contract_id].append(discount_id)

    for contract_id, discount_ids in contract_discounts.items():
        for start in range(0, len(discount_ids), UPDATE_BATCH_SIZE):
            Discount.objects.filter(
                pk__in=discount_ids[start : start + UPDATE_BATCH_SIZE]
            ).update(b2b_contract_id=contract_id)

    if ambiguous:
        log.warning(
            "Left %s enrollment code(s) without a contract, because their runs "
            "belong to several: discount ids %s",
            len(ambiguous),
            sorted(ambiguous),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("b2b", "0033_organizationpage_description_plain_text"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("courses", "0109_add_manufacturing_variant"),
        ("ecommerce", "0057_discount_b2b_contract"),
    ]

    operations = [
        migrations.RunPython(backfill_discount_contracts, migrations.RunPython.noop),
    ]
