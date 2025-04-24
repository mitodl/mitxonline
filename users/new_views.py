"""New Keycloak User views"""

from django.db import transaction
from rest_framework import mixins, viewsets

from hubspot_sync.task_helpers import sync_hubspot_user
from users.serializers import UserSerializer


class CurrentUserRetrieveUpdateViewSet(
    mixins.UpdateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """User retrieve and update viewsets for the current user"""

    serializer_class = UserSerializer
    permission_classes = []

    def get_object(self):
        """Returns the current request user"""
        # NOTE: this may be a logged in or anonymous user
        return self.request.user

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            update_result = super().update(request, *args, **kwargs)
            sync_hubspot_user(request.user)
            return update_result
