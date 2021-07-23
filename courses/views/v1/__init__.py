"""Course views verson 1"""
from rest_framework import status, viewsets, generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.api import get_user_enrollments
from courses.models import Course, CourseRun, Program, CourseRunEnrollment
from courses.serializers import (
    CourseRunEnrollmentSerializer,
    CourseRunSerializer,
    CourseSerializer,
    ProgramEnrollmentSerializer,
    ProgramSerializer,
)


class ProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Programs"""

    permission_classes = []

    serializer_class = ProgramSerializer
    queryset = Program.objects.filter(live=True)


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Courses"""

    permission_classes = []

    serializer_class = CourseSerializer
    queryset = Course.objects.filter(live=True)


class CourseRunViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for CourseRuns"""

    serializer_class = CourseRunSerializer
    queryset = CourseRun.objects.all()


class UserEnrollmentsView(generics.ListAPIView):
    """API view for user enrollments"""

    serializer_class = CourseRunEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            CourseRunEnrollment.objects.filter(user=self.request.user)
            .select_related("run__course__page")
            .all()
        )

    def get_serializer_context(self):
        return {"include_page_fields": True}
