"""
Contract provisioning for B2B (capability C3).

The steps of setting up a contract, pulled out of the b2b_contract,
b2b_courseware, b2b_codes and check_contract_variant commands so the commands
and the staff contract API do them the same way.
"""

import logging
from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from mitol.common.utils import now_in_utc
from opaque_keys import InvalidKeyError

from b2b.api import create_contract_run
from b2b.constants import (
    CONTRACT_SETUP_STATUS_COMPLETE,
    CONTRACT_SETUP_STATUS_FAILED,
    CONTRACT_SETUP_STATUS_IN_PROGRESS,
    PROVISIONING_ACTION_CONTRACT_VARIANT_ADDED,
    PROVISIONING_ACTION_CONTRACT_VARIANT_UPDATED,
)
from b2b.exceptions import ContractVariantError, SourceCourseIncompleteError
from b2b.models import ContractPage, ContractProgramItem, OrganizationPage
from b2b.provisioning import _audit
from b2b.tasks import queue_enrollment_code_check
from courses.models import Course, CourseRun, CourseRunEnrollment
from courses.retirement import (
    deactivate_run_products,
    get_run_products,
    push_run_dates_to_edx,
)
from ecommerce.models import Discount, DiscountProduct
from openedx.constants import (
    COURSE_RUN_CLONE_STATUS_CLONING,
    COURSE_RUN_CLONE_STATUS_FAILED,
    COURSE_RUN_CLONE_STATUS_PENDING,
)
from openedx.models import CourseRunClone
from openedx.tasks import clone_courserun
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
    the contract's active variant sets. no_reruns defaults to True, unlike
    create_contract_run, so repeating a call does not mint another run.
    org_prefix defaults to the organization's own prefix.
    """

    if filter_variants is None:
        filter_variants = list(contract.active_variant_options())

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


def queue_enrollment_code_check_if_required(contract: ContractPage):
    """
    Queue the enrollment code check for a contract that uses codes.

    Contracts that don't are skipped: for them the check strips codes, and
    that should stay a deliberate b2b_codes validate rather than a side effect
    of editing the contract.
    """

    if contract.requires_enrollment_codes:
        queue_enrollment_code_check.delay(contract.id)


def get_contract_setup_status(contract: ContractPage) -> dict:
    """
    Report how far a contract's setup has got.

    A contract run created without an edX clone (skip_edx, or before clones
    were tracked) has no clone status and does not hold the contract in
    progress.

    Returns a dict with `status` (a CONTRACT_SETUP_STATUS_* value), `runs` (the
    clone status, attempts and last error of each contract run) and
    `enrollment_codes` (how many the contract needs and how many it has).
    """

    runs = list(contract.get_course_runs().order_by("courseware_id"))
    clones = {
        clone.course_run_id: clone
        for clone in CourseRunClone.objects.filter(course_run__in=runs)
    }
    expected_codes = expected_enrollment_code_count(contract)
    existing_codes = contract.get_discounts().distinct().count()

    clone_statuses = {clone.status for clone in clones.values()}
    if COURSE_RUN_CLONE_STATUS_FAILED in clone_statuses:
        status = CONTRACT_SETUP_STATUS_FAILED
    elif (
        clone_statuses
        & {COURSE_RUN_CLONE_STATUS_PENDING, COURSE_RUN_CLONE_STATUS_CLONING}
        or existing_codes < expected_codes
    ):
        status = CONTRACT_SETUP_STATUS_IN_PROGRESS
    else:
        status = CONTRACT_SETUP_STATUS_COMPLETE

    run_statuses = []
    for run in runs:
        clone = clones.get(run.id)
        run_statuses.append(
            {
                "courseware_id": run.courseware_id,
                "clone_status": clone.status if clone else None,
                "clone_attempts": clone.attempts if clone else 0,
                "clone_error": clone.error if clone else "",
            }
        )

    return {
        "status": status,
        "runs": run_statuses,
        "enrollment_codes": {"expected": expected_codes, "existing": existing_codes},
    }


def retry_contract_setup(contract: ContractPage) -> list[CourseRunClone]:
    """
    Queue again the parts of a contract's setup that failed.

    Failed edX clones are re-queued. Clones still pending or running are left
    alone. The enrollment code check is queued for a contract that uses codes,
    since it converges.

    Returns the clones that were re-queued.
    """

    failed = list(
        CourseRunClone.objects.filter(
            course_run__b2b_contracts=contract,
            status=COURSE_RUN_CLONE_STATUS_FAILED,
        ).distinct()
    )
    for clone in failed:
        clone.status = COURSE_RUN_CLONE_STATUS_PENDING
        clone.save(update_fields=["status", "updated_on"])
        clone_courserun.delay(clone.course_run_id, clone.source_courseware_id)

    queue_enrollment_code_check_if_required(contract)

    return failed


def expire_unused_enrollment_codes(
    contract: ContractPage, *, dry_run: bool = False
) -> list[tuple[str, bool]]:
    """
    Take the contract's unused enrollment codes out of the contract.

    Each code is detached from the contract's products, and deleted if it
    applies to nothing else. Codes redeemed to enroll or to join the contract
    are left alone.

    Returns (code, deleted) for each code; with dry_run, what would happen.
    """

    contract_products = list(contract.get_products())
    expired = []

    for discount in list(contract.get_unused_discounts()):
        deleted = not discount.products.exclude(product__in=contract_products).exists()

        if not dry_run:
            discount.products.filter(product__in=contract_products).delete()
            if deleted:
                discount.delete()

        expired.append((discount.discount_code, deleted))

    return expired


def _variant_set_snapshot(contract: ContractPage, variant: SupportedVariant) -> dict:
    """Return the audited fields of a contract's variant set."""

    return {
        "contract_id": contract.id,
        "variant_id": variant.id,
        "language": variant.language,
        "variant_length": variant.variant_length,
        "variant_industry": variant.variant_industry,
        "default_variant": variant.default_variant,
        "active": variant.active,
        "b2b_only": variant.b2b_only,
    }


def _lock_contract_variant_sets(contract: ContractPage) -> None:
    """
    Serialize changes to a contract's variant sets.

    Nothing in the database stops two sets with the same language, length and
    industry, so the duplicate check is only safe under this lock. of=("self",)
    locks the contract's row and not the Wagtail page rows it joins.
    """

    ContractPage.objects.select_for_update(of=("self",)).get(pk=contract.pk)


def _variant_fields(variant) -> tuple[str, str, str]:
    return (variant.language, variant.variant_length, variant.variant_industry)


def get_contract_variant_coverage(contract: ContractPage) -> list[dict]:
    """
    Report what each of the contract's variant sets matches.

    The contract's courses are those of its runs and of its programs. For each
    variant set, a course is listed if one of its own active variant sets has
    the same language, length and industry. That is the condition
    add_courseware_to_contract uses to pick source runs, so a listed course
    with a source run and no contract run is one that adding courseware again
    would create a run for, as long as the set is active.

    Returns a dict per variant set, default first: `variant` (the
    SupportedVariant) and `courses`, each with `course`, `has_source_run` and
    `contract_run` (the contract's run for this variant, or None).
    """

    courses = list(
        Course.objects.filter(
            Q(in_programs__program__contract_memberships__contract=contract)
            | Q(courseruns__b2b_contracts=contract)
        )
        .distinct()
        .order_by("readable_id")
    )
    course_variants = {course.id: set() for course in courses}
    for variant in SupportedVariant.objects.filter(
        content_type=ContentType.objects.get_for_model(Course),
        object_id__in=course_variants,
        active=True,
    ):
        course_variants[variant.object_id].add(_variant_fields(variant))
    source_runs = {
        (run.course_id, *_variant_fields(run))
        for run in CourseRun.all_objects.filter(course__in=courses).filter(
            Q(is_source_run=True) | Q(run_tag="SOURCE")
        )
    }
    # Ascending, so the newest run for a course and variant is the one kept.
    contract_runs = {
        (run.course_id, *_variant_fields(run)): run
        for run in CourseRun.all_objects.filter(b2b_contracts=contract).order_by("id")
    }

    coverage = []
    for variant in contract.variant_options.order_by("-default_variant", "id"):
        fields = _variant_fields(variant)
        coverage.append(
            {
                "variant": variant,
                "courses": [
                    {
                        "course": course,
                        "has_source_run": (course.id, *fields) in source_runs,
                        "contract_run": contract_runs.get((course.id, *fields)),
                    }
                    for course in courses
                    if fields in course_variants[course.id]
                ],
            }
        )

    return coverage


def sync_contract_variants(contract: ContractPage, *, skip_edx: bool = False) -> dict:
    """
    Create the runs a contract's courses are missing for its variant sets.

    Adding a variant set creates no runs, so courseware added before the set
    has none for it. For each active set, this creates a run for every course
    get_contract_variant_coverage lists with a source run and no contract run.
    A course and variant that already has a run in the contract is left alone,
    so repeating the call creates nothing more.

    Returns a dict with `runs_created` (the new CourseRuns),
    `missing_source_runs` (a `course` and `variant` for each one that supports
    the set and has no source run to clone) and `failed` (the same pair for
    each one whose run could not be created). Queueing the enrollment code
    check is left to the caller.
    """

    runs_created = []
    missing_source_runs = []
    failed = []

    for entry in get_contract_variant_coverage(contract):
        variant = entry["variant"]
        if not variant.active:
            continue

        for listed in entry["courses"]:
            if listed["contract_run"] is not None:
                continue

            pair = {"course": listed["course"], "variant": variant}
            if not listed["has_source_run"]:
                missing_source_runs.append(pair)
                continue

            # One variant per call, so a failure belongs to one course and
            # variant and leaves the others' runs in place.
            try:
                created = create_contract_run(
                    contract,
                    listed["course"],
                    skip_edx=skip_edx,
                    no_reruns=True,
                    filter_variants=[variant],
                )
            except (SourceCourseIncompleteError, InvalidKeyError):
                log.warning(
                    "Could not create a %s run of %s for contract %s",
                    _variant_fields(variant),
                    listed["course"].readable_id,
                    contract.id,
                    exc_info=True,
                )
                failed.append(pair)
                continue

            # Nothing back means create_contract_run saw a run this report
            # didn't (e.g. one linked only by the old b2b_contract key), or the
            # course has no default variant and its source run wasn't matched.
            if not created:
                failed.append(pair)
                continue

            runs_created.extend(run for run, _ in created)

    return {
        "runs_created": runs_created,
        "missing_source_runs": missing_source_runs,
        "failed": failed,
    }


@transaction.atomic
def add_contract_variant_set(  # noqa: PLR0913
    contract: ContractPage,
    *,
    language: str,
    variant_length: str = "",
    variant_industry: str = "",
    b2b_only: bool = False,
    actor=None,
) -> SupportedVariant:
    """
    Add a non-default variant set to a contract.

    Every contract already has its default set (ensure_default_variant), so
    this never adds one. Creates no runs: adding courseware to the contract
    again does that.

    Raises ContractVariantError if the contract already has a set with the
    same language, length and industry, active or not.
    """

    _lock_contract_variant_sets(contract)
    existing = contract.variant_options.filter(
        language=language,
        variant_length=variant_length,
        variant_industry=variant_industry,
    ).first()
    if existing:
        msg = (
            f"The contract already has this variant set (id {existing.id}"
            f"{'' if existing.active else ', inactive'})."
        )
        raise ContractVariantError(msg)

    variant = SupportedVariant.objects.create(
        variant_object=contract,
        language=language,
        variant_length=variant_length,
        variant_industry=variant_industry,
        b2b_only=b2b_only,
        default_variant=False,
    )

    _audit(
        contract.organization,
        PROVISIONING_ACTION_CONTRACT_VARIANT_ADDED,
        actor=actor,
        data_after=_variant_set_snapshot(contract, variant),
    )

    return variant


@transaction.atomic
def update_contract_variant_set(
    contract: ContractPage,
    variant: SupportedVariant,
    *,
    active: bool | None = None,
    b2b_only: bool | None = None,
    actor=None,
) -> SupportedVariant:
    """
    Turn a contract's variant set on or off, or change its b2b_only flag.

    An inactive set gets no new runs and its runs are left out of the
    contract's course list (get_all_variant_runs). Its existing runs are not
    closed and enrollments in them are untouched, so turning the set back on
    restores it. Closing runs is what removing courseware is for.

    A change that changes nothing is not saved or audited.

    Raises ContractVariantError for a change to the default set: deactivating
    it would leave the contract's learners an empty course list, and the
    database refuses a b2b_only default.
    """

    if variant.default_variant and (active is False or b2b_only is True):
        msg = (
            "The contract's default variant set can't be deactivated or made B2B-only."
        )
        raise ContractVariantError(msg)

    _lock_contract_variant_sets(contract)
    variant.refresh_from_db()
    before = _variant_set_snapshot(contract, variant)
    if active is not None:
        variant.active = active
    if b2b_only is not None:
        variant.b2b_only = b2b_only
    after = _variant_set_snapshot(contract, variant)
    if after == before:
        return variant
    variant.save()

    _audit(
        contract.organization,
        PROVISIONING_ACTION_CONTRACT_VARIANT_UPDATED,
        actor=actor,
        data_before=before,
        data_after=after,
    )

    return variant
