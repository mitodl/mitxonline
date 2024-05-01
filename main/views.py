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


def get_base_context(request):
    """
    Returns the template context key/values needed for the base template and all templates that extend it
    """
    context = {
        "new_design": features.is_enabled(
            features.ENABLE_NEW_DESIGN,
            False,  # noqa: FBT003
            request.user.id if request.user.is_authenticated else "anonymousUser",
        ),
        "new_footer": features.is_enabled(
            features.ENABLE_NEW_FOOTER,
            False,  # noqa: FBT003
            request.user.id if request.user.is_authenticated else "anonymousUser",
        ),
    }

    if settings.GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE:
        context["domain_verification_tag"] = (
            settings.GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE
        )

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


def cms_signin_redirect_to_site_signin(request):  # noqa: ARG001
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
