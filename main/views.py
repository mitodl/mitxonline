"""
mitx_online views
"""
from django.shortcuts import render


def index(request):
    """
    The index view. Display available programs
    """

    return render(
        request,
        "index.html",
    )
