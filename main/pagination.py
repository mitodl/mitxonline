"""Shared pagination classes for REST APIs."""

from django.core.paginator import Paginator as DjangoPaginator
from django.utils.functional import cached_property
from rest_framework.pagination import PageNumberPagination


class CountOptimizedPaginator(DjangoPaginator):
    """
    Paginator whose count query only touches the primary key.

    A paginated response includes a ``count``, computed as a separate
    ``SELECT COUNT(*)`` wrapping the view's queryset. On a queryset carrying
    annotations and ``.distinct()``, the default ``object_list.count()`` wraps a
    subquery that selects every column the page would have selected - including
    aggregates that exist only to build the response body. Counting rows needs
    none of that.

    Note this hooks ``django.core.paginator.Paginator.count`` rather than DRF's
    ``get_count()``: ``get_count()`` only exists on ``LimitOffsetPagination``.
    ``PageNumberPagination`` reads ``self.page.paginator.count``, so overriding
    ``get_count()`` on a ``PageNumberPagination`` subclass would do nothing.
    """

    #: Override when a queryset is DISTINCT over *non-unique* columns
    #: specifically to collapse duplicate rows, since dropping those columns
    #: would change what "distinct" means and therefore change the count.
    count_fields = ("pk",)

    @cached_property
    def count(self):
        """
        Count distinct values of ``count_fields`` only.

        ``.values()`` rather than ``.only()``, because ``.only()`` does not
        reliably strip annotations out of the count subquery, and an annotation
        left in there is evaluated once per row counted.

        ``.order_by()`` is load-bearing, not cosmetic: for a ``DISTINCT`` query
        the SQL compiler appends every ``ORDER BY`` expression to the select
        list, so without it the inner query selects the ordering column too.
        """
        object_list = self.object_list
        if hasattr(object_list, "values"):
            return object_list.order_by().values(*self.count_fields).distinct().count()
        return super().count


class Pagination(PageNumberPagination):
    """Paginator class for infinite loading."""

    django_paginator_class = CountOptimizedPaginator
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100
