"""
Shared logic for retiring (delisting) course runs.

A "retired" run is one that has been made inert: it is no longer live, its
enrollment window and course window are in the past, and its products are
switched off. Existing enrollments are deliberately left alone by default so
that learners who were partway through the material keep their access.

The date changes are pushed to edX as well as written locally, because
``courses.api.sync_course_runs`` overwrites ``start_date``, ``end_date``,
``enrollment_start``, ``enrollment_end``, ``title``, ``is_self_paced`` and
``certificate_available_date`` from edX on every sync. ``live`` is the only
one of these fields that is not synced, which makes it the durable local lever.

This module is intentionally free of any B2B imports so that it can be used for
non-B2B runs. The B2B holding-contract behaviour lives in ``b2b.api``.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.contrib.contenttypes.models import ContentType
from mitol.common.utils.datetime import now_in_utc

from courses.models import (
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
)
from ecommerce.models import BasketItem, Discount, Product
from openedx.api import get_edx_course, update_edx_course

log = logging.getLogger(__name__)

# How far into the past to push the retired dates. A day is enough to put the
# run unambiguously in the past without looking like a data-entry error.
RETIREMENT_DATE_OFFSET = timedelta(days=1)


class SourceRunRetirementError(Exception):
    """Raised when the run being retired is a source run."""


@dataclass
class ProductAudit:
    """What we know about a product attached to the run."""

    product: Product
    was_active: bool
    discounts: list = field(default_factory=list)
    basket_items: int = 0


@dataclass
class RunAudit:
    """Everything the operator should see before a run is retired."""

    run: CourseRun
    active_enrollments: list = field(default_factory=list)
    inactive_enrollments: list = field(default_factory=list)
    products: list = field(default_factory=list)
    certificate_count: int = 0
    grade_count: int = 0
    edx_details: dict | None = None
    edx_error: str | None = None

    @property
    def has_active_enrollments(self):
        """Whether anybody is currently enrolled."""

        return len(self.active_enrollments) > 0


def get_run_products(run: CourseRun) -> list[Product]:
    """
    Return every product attached to the run, active or not.

    ``Product.objects`` is an ``ActiveUndeleteManager`` and filters out
    ``is_active=False``, so already-deactivated products are invisible through
    it. We want to see them, so this uses ``all_objects``.

    Args:
        run (CourseRun): the run to inspect.
    Returns:
        list of Product: the run's products, evaluated so that later updates
        don't mutate the collection out from under the caller.
    """

    return list(
        Product.all_objects.filter(
            content_type=ContentType.objects.get_for_model(CourseRun),
            object_id=run.id,
        ).all()
    )


def deactivate_run_products(run: CourseRun) -> list[Product]:
    """
    Switch off every active product attached to the run.

    Uses ``save()`` rather than a queryset ``update()`` so that the
    ``ecommerce.signals.sync_product`` post-save receiver still fires and
    HubSpot stays consistent. That means one HubSpot task per product.

    Args:
        run (CourseRun): the run whose products should be deactivated.
    Returns:
        list of Product: the products that were actually changed.
    """

    deactivated = []

    for product in get_run_products(run):
        if product.is_active:
            product.is_active = False
            product.save(update_fields=("is_active",))
            deactivated.append(product)

    return deactivated


def compute_retirement_dates(run: CourseRun, *, now: datetime | None = None) -> dict:
    """
    Work out the set of dates that put the run in the past.

    ``end_date`` and ``enrollment_end`` are the fields that actually delist a
    run: ``end_date`` drives ``CourseRun.is_past`` and
    ``CourseRunQuerySet.available()``, and ``enrollment_end`` drives
    ``CourseRun.is_enrollable``. The start dates are only moved if they aren't
    already early enough, because edX refuses to set enrollment dates unless
    the run has both a start and an end date, so we must always send a
    coherent set of four.

    Args:
        run (CourseRun): the run being retired.
    Keyword Args:
        now (datetime|None): override for the current time, for tests.
    Returns:
        dict: keys ``start``, ``end``, ``enrollment_start``, ``enrollment_end``.
    """

    now = now or now_in_utc()
    cutoff = now - RETIREMENT_DATE_OFFSET

    start = (
        run.start_date
        if run.start_date and run.start_date < cutoff
        else cutoff - RETIREMENT_DATE_OFFSET
    )
    enrollment_start = (
        run.enrollment_start
        if run.enrollment_start and run.enrollment_start < start
        else start
    )

    return {
        "start": start,
        "end": cutoff,
        "enrollment_start": enrollment_start,
        "enrollment_end": cutoff,
    }


def push_run_dates_to_edx(
    run: CourseRun, dates: dict | None = None, *, client=None
) -> bool:
    """
    Push a run's schedule to edX.

    edX will only accept enrollment dates for a run that has both a start and
    an end date, so if any of the four dates is missing this sends the title
    and pacing only and returns False. Callers that need the dates to stick
    should pass a complete set (see ``compute_retirement_dates``).

    Any error from the edX client propagates; it is up to the caller to decide
    whether that should abort the operation.

    Args:
        run (CourseRun): the run to update in edX.
        dates (dict|None): the dates to send. Defaults to the run's current
            local values.
    Keyword Args:
        client (EdxApi|None): edX client, if you want to reuse one.
    Returns:
        bool: True if the dates were included in the payload, False if only
        the title and pacing were sent.
    """

    if dates is None:
        dates = {
            "start": run.start_date,
            "end": run.end_date,
            "enrollment_start": run.enrollment_start,
            "enrollment_end": run.enrollment_end,
        }

    complete = all(dates.get(key) for key in ("start", "end"))
    enrollment_complete = complete and all(
        dates.get(key) for key in ("enrollment_start", "enrollment_end")
    )

    payload = {
        "title": run.title,
        "pacing_type": "self_paced" if run.is_self_paced else "instructor_paced",
    }

    if complete:
        payload["start"] = dates["start"]
        payload["end"] = dates["end"]

        if enrollment_complete:
            payload["enrollment_start"] = dates["enrollment_start"]
            payload["enrollment_end"] = dates["enrollment_end"]

    if not enrollment_complete:
        log.warning(
            "push_run_dates_to_edx: %s has an incomplete date set %s, so edX will "
            "not accept the enrollment window and the next sync will overwrite "
            "the local values",
            run.courseware_id,
            dates,
        )

    update_edx_course(run.courseware_id, client=client, **payload)

    return enrollment_complete


def audit_course_run(
    run: CourseRun, *, fetch_edx: bool = True, client=None
) -> RunAudit:
    """
    Collect everything an operator needs to see before retiring a run.

    Makes no changes. Safe to call in dry-run mode.

    Args:
        run (CourseRun): the run to inspect.
    Keyword Args:
        fetch_edx (bool): whether to read the run's current state from edX.
        client (EdxApi|None): edX client, if you want to reuse one.
    Returns:
        RunAudit
    """

    audit = RunAudit(run=run)

    enrollments = (
        CourseRunEnrollment.all_objects.filter(run=run)
        .select_related("user")
        .order_by("user__email")
    )

    for enrollment in enrollments:
        if enrollment.active:
            audit.active_enrollments.append(enrollment)
        else:
            audit.inactive_enrollments.append(enrollment)

    # all_objects, because CourseRunCertificate.objects hides revoked
    # certificates and ones with a future issue date. Under-reporting here would
    # be exactly the wrong direction for a warning.
    audit.certificate_count = CourseRunCertificate.all_objects.filter(
        course_run=run
    ).count()
    audit.grade_count = CourseRunGrade.objects.filter(course_run=run).count()

    for product in get_run_products(run):
        audit.products.append(
            ProductAudit(
                product=product,
                was_active=product.is_active,
                discounts=list(
                    Discount.objects.filter(products__product=product).distinct().all()
                ),
                basket_items=BasketItem.objects.filter(product=product).count(),
            )
        )

    if fetch_edx:
        try:
            edx_run = get_edx_course(run.courseware_id, client=client)

            def _edx_value(attr, edx_run=edx_run):
                """Stringify an edX attribute, keeping None as None."""
                value = getattr(edx_run, attr, None)
                return None if value is None else str(value)

            audit.edx_details = {
                attr: _edx_value(attr)
                for attr in (
                    "title",
                    "start",
                    "end",
                    "enrollment_start",
                    "enrollment_end",
                )
            }
        except Exception as exc:  # noqa: BLE001
            audit.edx_error = str(exc)

    return audit


def check_run_retirable(run: CourseRun) -> None:
    """
    Refuse to retire runs that other machinery depends on.

    Source runs are the templates ``b2b.api.create_contract_run`` clones from,
    so retiring one quietly breaks every future contract run for the course.
    There is deliberately no override flag.

    Args:
        run (CourseRun): the run to check.
    Raises:
        SourceRunRetirementError: if the run is a source run.
    """

    if run.is_source_run or run.run_tag == "SOURCE":
        msg = (
            f"{run.courseware_id} is a source run. Retiring it would break future "
            "contract runs for this course. Retire the contract runs instead."
        )
        raise SourceRunRetirementError(msg)


def build_snapshot(audit: RunAudit, *, reason: str = "", source: str = "") -> dict:
    """
    Build a JSON-serialisable record of the run's pre-retirement state.

    This is the rollback source of truth. There is no automated rollback; the
    snapshot exists so that a human can put things back by hand.

    Args:
        audit (RunAudit): the audit to serialise.
    Keyword Args:
        reason (str): why the run is being retired.
        source (str): what produced the snapshot, e.g. "Management Command".
    Returns:
        dict
    """

    run = audit.run

    def _dt(value):
        return value.isoformat() if value else None

    return {
        "snapshot_taken": now_in_utc().isoformat(),
        "reason": reason,
        "source": source,
        "run": {
            "id": run.id,
            "courseware_id": run.courseware_id,
            "course": run.course.readable_id,
            "run_tag": run.run_tag,
            "title": run.title,
            "live": run.live,
            "is_self_paced": run.is_self_paced,
            "is_source_run": run.is_source_run,
            "language": run.language,
            "start_date": _dt(run.start_date),
            "end_date": _dt(run.end_date),
            "enrollment_start": _dt(run.enrollment_start),
            "enrollment_end": _dt(run.enrollment_end),
            "expiration_date": _dt(run.expiration_date),
            "upgrade_deadline": _dt(run.upgrade_deadline),
            "b2b_contract_id": run.b2b_contract_id,
        },
        "edx": audit.edx_details,
        "edx_error": audit.edx_error,
        "products": [
            {
                "id": entry.product.id,
                "description": entry.product.description,
                "price": str(entry.product.price),
                "is_active": entry.was_active,
                "basket_items": entry.basket_items,
                "discounts": [
                    {"id": discount.id, "code": discount.discount_code}
                    for discount in entry.discounts
                ],
            }
            for entry in audit.products
        ],
        "enrollments": {
            "active": [
                {"id": e.id, "user": e.user.email, "mode": e.enrollment_mode}
                for e in audit.active_enrollments
            ],
            "inactive": [
                {
                    "id": e.id,
                    "user": e.user.email,
                    "mode": e.enrollment_mode,
                    "change_status": e.change_status,
                }
                for e in audit.inactive_enrollments
            ],
        },
        "certificate_count": audit.certificate_count,
        "grade_count": audit.grade_count,
    }


def retire_course_run(
    run: CourseRun,
    *,
    deactivate_products: bool = True,
    skip_edx: bool = False,
    edx_client=None,
    now: datetime | None = None,
) -> dict:
    """
    Retire a course run: past dates in edX and locally, not live, products off.

    edX is written first, deliberately. edX is the effective source of truth
    for the date fields, so if the edX call fails after we've written locally
    the next ``sync_course_runs`` pass would silently revert us. Writing edX
    first means a failure aborts with nothing changed, and a local failure
    after a successful edX write is self-healing on the next sync.

    Enrollments are not touched. Unenrolling is a separate, explicit step
    (see ``courses.management.utils.bulk_unenroll_learners``) because it
    revokes courseware access and emails learners.

    Args:
        run (CourseRun): the run to retire.
    Keyword Args:
        deactivate_products (bool): switch off the run's products.
        skip_edx (bool): don't call edX at all, for runs with no edX counterpart.
        edx_client (EdxApi|None): edX client, if you want to reuse one.
        now (datetime|None): override for the current time, for tests.
    Returns:
        dict: ``dates`` applied, ``products`` deactivated, and ``edx_updated``.
    """

    dates = compute_retirement_dates(run, now=now)
    edx_updated = False

    if not skip_edx:
        edx_updated = push_run_dates_to_edx(run, dates, client=edx_client)

    # CourseRun.save() runs clean(), which rejects an expiration_date earlier
    # than the start or end date. Pushing the run into the past would trip that
    # for any run whose expiration_date has already passed - which is the most
    # likely thing to be retiring. Clear it so it goes back to being derived,
    # exactly as sync_course_runs does when the dates change under it.
    if run.expiration_date and (
        run.expiration_date < dates["end"] or run.expiration_date < dates["start"]
    ):
        log.info(
            "Clearing expiration_date %s on %s; it predates the retired end date",
            run.expiration_date,
            run.courseware_id,
        )
        run.expiration_date = None

    run.start_date = dates["start"]
    run.end_date = dates["end"]
    run.enrollment_start = dates["enrollment_start"]
    run.enrollment_end = dates["enrollment_end"]
    run.live = False
    run.save()

    products = deactivate_run_products(run) if deactivate_products else []

    log.info(
        "Retired course run %s (edx_updated=%s, products_deactivated=%s)",
        run.courseware_id,
        edx_updated,
        len(products),
    )

    return {
        "dates": dates,
        "products": products,
        "edx_updated": edx_updated,
    }
