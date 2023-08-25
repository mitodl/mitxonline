"""
mitx_online views
"""
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseNotFound, HttpResponseServerError
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import never_cache
from rest_framework.pagination import LimitOffsetPagination
from main import features

from main.features import is_enabled


def get_base_context(request):
    """
    Returns the template context key/values needed for the base template and all templates that extend it
    """
    context = {"new_design": is_enabled("mitxonline-new-product-page", False)}

    if settings.GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE:
        context[
            "domain_verification_tag"
        ] = settings.GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE

    return context


@never_cache
def index(request, **kwargs):
    """
    The index view. Display available programs
    """
    context = get_base_context(request)
    return render(request, "index.html", context=context)


def catalog(request, **kwargs):
    """
    The catalog view.
    """
    if features.is_enabled(features.ENABLE_NEW_DESIGN):
        context = get_base_context(request)
        return render(request, "index.html", context=context)
    return handler404(request)


@never_cache
def refine(request, **kwargs):
    """
    The refine view for the staff dashboard
    """
    return render(request, "refine.html", context=get_base_context(request))


def handler404(request, *args):  # pylint: disable=unused-argument
    """404: NOT FOUND ERROR handler"""
    context = get_base_context(request)
    return HttpResponseNotFound(
        render_to_string("404.html", request=request, context=get_base_context(request))
    )


def handler500(request):
    """500 INTERNAL SERVER ERROR handler"""
    return HttpResponseServerError(
        render_to_string("500.html", request=request, context=get_base_context(request))
    )


def cms_signin_redirect_to_site_signin(request):
    """Redirect wagtail admin signin to site signin page"""
    return redirect_to_login(reverse("wagtailadmin_home"), login_url="/signin")


class RefinePagination(LimitOffsetPagination):
    """
    A pagination class that uses the default Refine limit and offset parameters.
    """

    default_limit = 10
    limit_query_param = "l"
    offset_query_param = "o"
    max_limit = 50
