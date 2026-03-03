"""
mitx_online views
"""

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import (
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponseServerError,
)
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import never_cache
from mitol.olposthog.features import is_enabled
from rest_framework.pagination import LimitOffsetPagination

from main import features


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
def index(request, **kwargs):
    """
    The index view. Display available programs
    """
    context = {**get_base_context(request), **kwargs}
    return render(request, "index.html", context=context)


@never_cache
def dashboard(request, **kwargs):
    """
    Dashboard view - redirects to the new learn frontend if the feature flag
    is enabled for this user, otherwise serves the legacy React app.
    """
    if request.user.is_authenticated:
        global_id = request.user.global_id
        if global_id and is_enabled(
            features.REDIRECT_LEARN_DASHBOARD, opt_unique_id=global_id
        ):
            redirect_url = settings.MIT_LEARN_DASHBOARD_URL
            if qs := request.META.get("QUERY_STRING"):
                redirect_url = f"{redirect_url}?{qs}"
            return HttpResponseRedirect(redirect_url)
    return index(request, **kwargs)


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
    # Redirect to /cms/ after login, not to wagtailadmin_home to avoid redirect loops
    cms_url = request.build_absolute_uri("/cms/")
    return redirect_to_login(cms_url, login_url=reverse("gateway-login"))


def staff_dashboard_signin_redirect_to_site_signin(request):
    """Staff dashboard signin redirect to site signin page."""
    # Only redirect if user is not authenticated
    if not request.user.is_authenticated:
        staff_dashboard_url = request.build_absolute_uri("/staff-dashboard/")
        return redirect_to_login(
            staff_dashboard_url, login_url=reverse("gateway-login")
        )

    return refine(request)


class RefinePagination(LimitOffsetPagination):
    """
    A pagination class that uses the default Refine limit and offset parameters.
    """

    default_limit = 10
    limit_query_param = "l"
    offset_query_param = "o"
    max_limit = 50
