import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from cms.models import InstructorPage
from cms.serializers import InstructorPageSerializer


@api_view(["GET"])
def instructor_page(request, id, format=None):
    try:
        page = InstructorPage.objects.get(pk=id)
    except Exception:
        logging.debug("got exception")
        return "nope"

    return Response(InstructorPageSerializer(page).data)
