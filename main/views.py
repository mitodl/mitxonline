"""
mitx_online views
"""

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import (
    HttpResponseNotFound,
    HttpResponseServerError,
)
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import never_cache
from rest_framework.pagination import LimitOffsetPagination


def get_base_context(request):  # noqa: ARG001
    """
    Returns the template context key/values needed for the base template and all templates that extend it
    """
    context = {}
    if settings.GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE:
        context["domain_verification_tag"] = (
            settings.GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE
        )
    context["hijack_logout_redirect_url"] = settings.HIJACK_LOGOUT_REDIRECT_URL

    return context


@never_cache
def index(request, **kwargs):  # noqa: ARG001
    """
    The index view. Display available programs
    """
    context = get_base_context(request)
    return render(request, "index.html", context=context)


@never_cache
def refine(request, **kwargs):  # noqa: ARG001
    """
    The refine view for the staff dashboard
    """
    return render(request, "refine.html", context=get_base_context(request))


def handler404(request, exception):  # pylint: disable=unused-argument  # noqa: ARG001
    """404: NOT FOUND ERROR handler"""
    context = get_base_context(request)  # noqa: F841
    return HttpResponseNotFound(
        render_to_string("404.html", request=request, context=get_base_context(request))
    )


def handler500(request):
    """500 INTERNAL SERVER ERROR handler"""
    return HttpResponseServerError(
        render_to_string("500.html", request=request, context=get_base_context(request))
    )


def cms_signin_redirect_to_site_signin(request):
    """CMS signin redirect to site signin page."""
    return redirect_to_login(
        reverse("wagtailadmin_home"), login_url=reverse("gateway-login")
    )


def staff_dashboard_signin_redirect_to_site_signin(request):
    """Staff dashboard signin redirect to site signin page."""
    # For staff dashboard, we want to redirect to the staff dashboard main page after login
    staff_dashboard_url = request.build_absolute_uri("/staff-dashboard/")
    return redirect_to_login(staff_dashboard_url, login_url=reverse("gateway-login"))


class RefinePagination(LimitOffsetPagination):
    """
    A pagination class that uses the default Refine limit and offset parameters.
    """

    default_limit = 10
    limit_query_param = "l"
    offset_query_param = "o"
    max_limit = 50
