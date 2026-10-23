"""Data gathering for the read-only user debug screen in the Django Admin"""

from django.db.models import Count
from django.urls import NoReverseMatch, reverse

from b2b.models import UserB2BContract, UserOrganization
from courses.models import (
    CourseRunCertificate,
    CourseRunEnrollment,
    ProgramCertificate,
    ProgramEnrollment,
)
from ecommerce.models import Order
from flexiblepricing.models import FlexiblePrice
from openedx.models import OpenEdxUser
from users.models import LegalAddress


def admin_change_url(obj):
    """
    Return the Django Admin change URL for obj, or None if obj is None or its
    model isn't registered in the admin.
    """

    if obj is None:
        return None

    opts = obj._meta  # noqa: SLF001
    try:
        return reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk]
        )
    except NoReverseMatch:
        return None


def _get_summary(user):
    """Return the user's basic info, edX user records and legal address."""

    try:
        legal_address = user.legal_address
    except LegalAddress.DoesNotExist:
        legal_address = None

    return {
        "edx_users": list(
            OpenEdxUser.objects.filter(user=user).order_by("platform", "id")
        ),
        "legal_address": legal_address,
    }


def _get_enrollments(user):
    """
    Return the user's program and course run enrollments, active or not, each
    paired with the certificate (revoked or not) for that program or run.
    """

    program_certs = {
        cert.program_id: cert
        for cert in ProgramCertificate.all_objects.filter(user=user)
    }
    run_certs = {
        cert.course_run_id: cert
        for cert in CourseRunCertificate.all_objects.filter(user=user)
    }

    program_enrollments = [
        {
            "enrollment": enrollment,
            "url": admin_change_url(enrollment),
            "program_url": admin_change_url(enrollment.program),
            "certificate": program_certs.get(enrollment.program_id),
            "certificate_url": admin_change_url(
                program_certs.get(enrollment.program_id)
            ),
            "contract_url": admin_change_url(enrollment.b2b_contract),
        }
        for enrollment in ProgramEnrollment.all_objects.filter(user=user)
        .select_related("program", "b2b_contract")
        .order_by("program__readable_id")
    ]

    run_enrollments = [
        {
            "enrollment": enrollment,
            "url": admin_change_url(enrollment),
            "run_url": admin_change_url(enrollment.run),
            "certificate": run_certs.get(enrollment.run_id),
            "certificate_url": admin_change_url(run_certs.get(enrollment.run_id)),
            "contract_url": admin_change_url(enrollment.b2b_contract),
        }
        for enrollment in CourseRunEnrollment.all_objects.filter(user=user)
        .select_related("run__course", "b2b_contract")
        .order_by("run__courseware_id")
    ]

    return {
        "program_enrollments": program_enrollments,
        "run_enrollments": run_enrollments,
    }


def _get_b2b(user):
    """
    Return the user's organization memberships and contract attachments,
    grouped by organization.

    Each group has the membership (None when the user is attached to a
    contract in an org they're not a member of) and a possibly empty list of
    contract attachments.
    """

    groups = {}

    def _group_for(org):
        if org.id not in groups:
            groups[org.id] = {
                "organization": org,
                "organization_url": admin_change_url(org),
                "membership": None,
                "membership_url": None,
                "contracts": [],
            }
        return groups[org.id]

    for membership in UserOrganization.objects.filter(user=user).select_related(
        "organization"
    ):
        group = _group_for(membership.organization)
        group["membership"] = membership
        group["membership_url"] = admin_change_url(membership)

    for attachment in UserB2BContract.objects.filter(user=user).select_related(
        "contract_page__organization"
    ):
        contract = attachment.contract_page
        _group_for(contract.organization)["contracts"].append(
            {
                "attachment": attachment,
                "contract": contract,
                "contract_url": admin_change_url(contract),
            }
        )

    for group in groups.values():
        group["contracts"].sort(key=lambda item: item["contract"].name)

    return sorted(groups.values(), key=lambda group: group["organization"].name)


def _get_orders(user):
    """Return a summary of the user's orders, newest first."""

    return [
        {"order": order, "url": admin_change_url(order)}
        for order in Order.objects.filter(purchaser=user)
        .annotate(line_count=Count("lines"))
        .order_by("-created_on")
    ]


def _get_flexible_prices(user):
    """Return a summary of the user's financial assistance requests."""

    return [
        {
            "request": flexible_price,
            "url": admin_change_url(flexible_price),
            "tier": flexible_price.tier if flexible_price.is_approved() else None,
            "courseware": flexible_price.courseware_object,
            "courseware_url": admin_change_url(flexible_price.courseware_object),
        }
        for flexible_price in FlexiblePrice.objects.filter(user=user)
        .select_related("tier__discount")
        .prefetch_related("courseware_object")
        .order_by("-created_on")
    ]


def get_user_debug_context(user):
    """Return everything the user debug screen displays for the user."""

    return {
        "debug_user": user,
        "summary": _get_summary(user),
        "enrollments": _get_enrollments(user),
        "b2b_groups": _get_b2b(user),
        "orders": _get_orders(user),
        "flexible_prices": _get_flexible_prices(user),
    }
