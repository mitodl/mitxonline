"""
mitx_online views
"""
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseNotFound, HttpResponseServerError
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import never_cache
from rest_framework.pagination import LimitOffsetPagination


@never_cache
def index(request, **kwargs):
    """
    The index view. Display available programs
    """
    return render(
        request,
        "index.html",
    )


@never_cache
def refine(request, **kwargs):
    """
    The refine view for the staff dashboard
    """
    return render(
        request,
        "refine.html",
    )


def handler404(request, exception):  # pylint: disable=unused-argument
    """404: NOT FOUND ERROR handler"""
    return HttpResponseNotFound(render_to_string("404.html", request=request))


def handler500(request):
    """500 INTERNAL SERVER ERROR handler"""
    return HttpResponseServerError(render_to_string("500.html", request=request))


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
