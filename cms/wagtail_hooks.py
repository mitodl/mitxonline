"""Custom hooks to configure wagtail behavior"""

from typing import List  # noqa: UP035

from django.shortcuts import redirect
from django.urls import reverse
from wagtail import hooks
from wagtail.admin import messages
from wagtail.admin.api.views import PagesAdminAPIViewSet
from wagtail.models import Page, Revision

from courses.models import CourseRunCertificate, ProgramCertificate

DEFAULT_ORDER = (
    "{prefix}coursepage__course__readable_id".format(prefix=""),
    "title",
)


def parse_ordering_params(param: List[str]) -> List[str]:  # noqa: UP006
    """
    Ignores the request to sort by "ord".
    Returns a sorting order based on the params and includes "readable_id"
    sorting in passed params if the sorting request contains title
    otherwise, it returns the requested order.
    """
    if "ord" in param:
        order = []
    elif "title" in param:
        prefix = "-" if param[0] == "-" else ""
        order = [f"{prefix}coursepage__course__readable_id", param]
    else:
        order = [param]
    return order


@hooks.register("construct_explorer_page_queryset")
def sort_pages_alphabetically(parent_page, pages, request):  # pylint: disable=unused-argument  # noqa: ARG001
    """Sort all pages by title alphabetically if no ordering is speacified"""
    order = DEFAULT_ORDER
    if request.GET.get("ordering"):
        order = parse_ordering_params(request.GET.get("ordering"))
    return pages.order_by(*order)


class OrderedPagesAPIEndpoint(PagesAdminAPIViewSet):
    """A clone of the default Wagtail admin API that additionally orders all responses by page title alphabetically"""

    def filter_queryset(self, queryset):
        """Sort all pages by title alphabetically"""
        return super().filter_queryset(queryset).order_by(*DEFAULT_ORDER)


@hooks.register("construct_admin_api")
def configure_admin_api_default_order(router):
    """Swap admin pages API for our own flavor that orders results by title"""
    router.register_endpoint("pages", OrderedPagesAPIEndpoint)


@hooks.register("before_delete_page")
def block_deleting_pages_with_certificate_revisions(request, page):
    """
    Refuse to delete a page if certificates point at a revision of it or of
    one of its descendants (e.g. a course page's certificate page).

    Certificates reference their certificate page revision with PROTECT, so
    the delete would otherwise fail with a ProtectedError and a 500. Wagtail's
    own protected-reference check doesn't catch it, since the reference is to
    a revision rather than the page.
    """
    page_ids = [
        str(page_id)
        for page_id in Page.objects.descendant_of(page, inclusive=True).values_list(
            "id", flat=True
        )
    ]
    revisions = Revision.page_revisions.filter(object_id__in=page_ids)
    certificate_counts = [
        (
            model.all_objects.filter(certificate_page_revision__in=revisions).count(),
            label,
        )
        for model, label in (
            (CourseRunCertificate, "course run certificate(s)"),
            (ProgramCertificate, "program certificate(s)"),
        )
    ]
    certificate_counts = [
        (count, label) for count, label in certificate_counts if count
    ]
    if not certificate_counts:
        return None

    messages.error(
        request,
        f"Can't delete '{page.get_admin_display_title()}': "
        + " and ".join(f"{count} {label}" for count, label in certificate_counts)
        + " point at revisions of this page or its certificate page. "
        "Unpublish it instead.",
    )
    return redirect(reverse("wagtailadmin_pages:edit", args=(page.id,)))
