

from courses.views.v1 import Pagination

Pagination()

class ProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Programs"""

    permission_classes = []

    serializer_class = ProgramSerializer
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["id", "live", "readable_id"]
    queryset = Program.objects.filter().prefetch_related("departments")
