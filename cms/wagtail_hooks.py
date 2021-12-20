"""Custom hooks to configure wagtail behavior"""
from typing import List
from wagtail.admin.api.views import PagesAdminAPIViewSet
from wagtail.core import hooks

DEFAULT_ORDER = (
    "{prefix}coursepage__course__readable_id".format(prefix=""),
    "title",
)


def parse_ordering_params(param: List[str]) -> List[str]:
    """
    Ignores the request to sort by "ord".
    Returns a sorting order based on the params and includes "readable_id"
    sorting in passed params if the sorting request contains title 
    otherwise, it returns the requested order.
    """
    if "ord" in param:
        order = []
    elif "title" in param:
        prefix= "-" if param[0]=="-" else ""
        order =  [
            "{prefix}coursepage__course__readable_id".format(
                prefix=prefix),
            param
            ]
    else:
        order = [param]
    return order

@hooks.register("construct_explorer_page_queryset")
def sort_pages_alphabetically(
    parent_page, pages, request
):  # pylint: disable=unused-argument
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
