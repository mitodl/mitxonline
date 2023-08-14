import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

from cms.models import InstructorPage
from cms.serializers import InstructorPageSerializer


@api_view(["GET"])
def instructor_page(request, id, format=None):
    page = InstructorPage.objects.get(pk=id)

    return Response(InstructorPageSerializer(page).data)
