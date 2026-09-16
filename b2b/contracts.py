"""
Contract provisioning for B2B (capability C3).

The steps of setting up a contract, pulled out of the b2b_contract,
b2b_courseware, b2b_codes and check_contract_variant commands so the commands
and the staff contract API do them the same way.
"""

import logging
from dataclasses import dataclass

from django.db import transaction
from mitol.common.utils import now_in_utc

from b2b.api import create_contract_run
from b2b.models import ContractPage, ContractProgramItem, OrganizationPage
from courses.models import CourseRun, CourseRunEnrollment
from courses.retirement import (
    deactivate_run_products,
    get_run_products,
    push_run_dates_to_edx,
)
from ecommerce.models import Discount, DiscountProduct
from variants.models import SupportedVariant

log = logging.getLogger(__name__)

DEFAULT_CONTRACT_VARIANT_LANGUAGE = "en"


@dataclass
class CoursewareAddition:
    """What adding one courseware object to a contract did."""

    runs_added: int = 0
    courses_without_source_run: int = 0
    skipped_reason: str = ""


def ensure_default_variant(contract: ContractPage) -> SupportedVariant:
    """
    Return the contract's default variant set, creating one if it has none.

    get_all_variant_runs returns nothing for a contract with no default variant,
    so its learners would see an empty contract.
    """

    return contract.variant_options.filter(
        default_variant=True
    ).first() or SupportedVariant.objects.create(
        variant_object=contract,
        language=DEFAULT_CONTRACT_VARIANT_LANGUAGE,
        b2b_only=False,
        default_variant=True,
    )


@transaction.atomic
def create_contract(  # noqa: PLR0913
    organization: OrganizationPage,
    *,
    name: str,
    membership_type: str,
    description: str = "",
    welcome_message: str = "",
    contract_start=None,
    contract_end=None,
    max_learners: int | None = None,
    enrollment_fixed_price=None,
) -> ContractPage:
    """
    Create a contract under an organization, with a default variant set.

    Creates no courseware and no enrollment codes.
    """

    contract = ContractPage(
        name=name,
        membership_type=membership_type,
        organization=organization,
        description=description,
        welcome_message=welcome_message,
        contract_start=contract_start,
        contract_end=contract_end,
        max_learners=max_learners,
        enrollment_fixed_price=enrollment_fixed_price,
    )
    organization.add_child(instance=contract)
    contract.save()
    ensure_default_variant(contract)

    return contract


def add_courseware_to_contract(  # noqa: PLR0913
    contract: ContractPage,
    courseware,
    *,
    skip_edx: bool = False,
    no_reruns: bool = True,
    org_prefix: str | None = None,
    ignore_langs: bool = False,
    only_lang: str | None = None,
    filter_variants: list | None = None,
) -> CoursewareAddition:
    """
    Add a program, course or course run to a contract.

    - A program gets contract runs for each of its courses that has a source
      run, and is linked to the contract.
    - A course gets contract runs from its source runs.
    - An existing run is attached as it is. A run already in another contract
      is left there and reported as skipped: a run can legitimately belong to
      more than one contract, and moving it out of one silently takes its
      learners' courseware with it.

    Runs are created for the variant sets in filter_variants, which defaults to
    every variant set on the contract. no_reruns defaults to True, unlike
    create_contract_run, so repeating a call does not mint another run.
    org_prefix defaults to the organization's own prefix.
    """

    if filter_variants is None:
        filter_variants = list(contract.variant_options.all())

    if courseware.is_program:
        runs_added, no_source = contract.add_program_courses(
            courseware,
            skip_edx=skip_edx,
            no_reruns=no_reruns,
            org_prefix=org_prefix,
            ignore_langs=ignore_langs,
            only_lang=only_lang,
            filter_variants=filter_variants,
        )
        return CoursewareAddition(
            runs_added=runs_added, courses_without_source_run=no_source
        )

    if courseware.is_run:
        if courseware.b2b_contracts.filter(id=contract.id).exists():
            return CoursewareAddition(
                skipped_reason=(
                    f"Run '{courseware.courseware_id}' is already in this contract."
                )
            )

        other_contract = courseware.b2b_contracts.exclude(id=contract.id).first()
        if other_contract:
            return CoursewareAddition(
                skipped_reason=(
                    f"Run '{courseware.courseware_id}' is already in {other_contract}."
                )
            )

        courseware.b2b_contract = contract
        courseware.save()
        courseware.b2b_contracts.add(contract)
        return CoursewareAddition(runs_added=1)

    created = create_contract_run(
        contract,
        courseware,
        skip_edx=skip_edx,
        org_prefix=org_prefix,
        no_reruns=no_reruns,
        ignore_langs=ignore_langs,
        only_lang=only_lang,
        filter_variants=filter_variants,
    )
    return CoursewareAddition(runs_added=len(created))


def _remove_run_from_contract(contract: ContractPage, run: CourseRun) -> bool:
    """
    Close a contract run to new enrollments and take it out of the contract.

    The run is closed and its products deactivated either way. It is unlinked
    only when nobody has enrolled in it, so enrolled learners keep their course.
    Enrollment codes left applying to no product, and never redeemed, are
    deleted.

    Returns True if the run was unlinked.
    """

    unlinked = not CourseRunEnrollment.objects.filter(run=run).exists()

    now = now_in_utc()
    if run.live or run.enrollment_end is None or run.enrollment_end > now:
        run.live = False
        run.enrollment_end = now

    if unlinked:
        if run.b2b_contract == contract:
            run.b2b_contract = None
        run.b2b_contracts.remove(contract)

    run.save()

    # get_run_products uses all_objects so it finds products regardless of
    # their current is_active state, and returns a list so the deactivation
    # below doesn't mutate the collection reused when removing discount
    # associations. Shared with the retire_courserun command.
    run_products = get_run_products(run)
    deactivate_run_products(run)

    for discount in Discount.objects.filter(
        products__product__in=run_products
    ).distinct():
        DiscountProduct.objects.filter(
            discount=discount, product__in=run_products
        ).delete()

        if discount.products.count() == 0 and not (
            discount.order_redemptions.exists()
            or discount.contract_redemptions.exists()
        ):
            discount.delete()

    # Push the new enrollment_end to edX so the next sync from edX doesn't
    # overwrite it. edX will not accept an enrollment window for a run with no
    # start and end date, so for a run with a null end_date the new
    # enrollment_end never reaches edX and the next sync reverts it.
    # push_run_dates_to_edx returns False and logs a warning in that case.
    # Fixing that means also moving end_date into the past, which is what the
    # retire_courserun command does.
    try:
        push_run_dates_to_edx(run)
    except Exception:
        log.exception(
            "Failed to update enrollment end date on edX for %s", run.courseware_id
        )

    return unlinked


def remove_courseware_from_contract(
    contract: ContractPage, courseware, *, remove_program_runs: bool = False
) -> list[tuple[CourseRun, bool]]:
    """
    Remove a program, course or course run from a contract.

    A program is unlinked from the contract, and its contract runs are removed
    too only if remove_program_runs is set. A course has no link of its own, so
    removing it removes its contract runs. Only runs in this contract are
    touched.

    Returns (run, unlinked) for each run removed; see _remove_run_from_contract.
    """

    contract_runs = CourseRun.objects.filter(b2b_contracts=contract)

    if courseware.is_program:
        runs = (
            list(
                contract_runs.filter(
                    course__in=[course for course, _ in courseware.courses]
                )
            )
            if remove_program_runs
            else []
        )
        ContractProgramItem.objects.filter(
            contract=contract, program=courseware
        ).delete()
    elif courseware.is_run:
        runs = list(contract_runs.filter(id=courseware.id))
    else:
        runs = list(contract_runs.filter(course=courseware))

    return [(run, _remove_run_from_contract(contract, run)) for run in runs]


def expected_enrollment_code_count(contract: ContractPage) -> int:
    """
    Return how many enrollment codes the contract should have.

    Zero when learners join without codes (managed or auto membership with no
    price). Otherwise one unlimited-use code per product, or max_learners
    one-time codes per product when seats are capped. That is the per-product
    basis ensure_enrollment_codes_exist creates codes on, so a removed run that
    stays linked because of its enrollments, whose product is inactive, is not
    counted.
    """

    if not contract.requires_enrollment_codes:
        return 0

    product_count = contract.get_products().count()

    return product_count * (contract.max_learners or 1)
