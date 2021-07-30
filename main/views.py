"""
mitx_online views
"""
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.urls import reverse


def index(request, **kwargs):
    """
    The index view. Display available programs
    """

    return render(
        request,
        "index.html",
    )


def cms_signin_redirect_to_site_signin(request):
    """Redirect wagtail admin signin to site signin page"""
    return redirect_to_login(reverse("wagtailadmin_home"), login_url="/signin")
