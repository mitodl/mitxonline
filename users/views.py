"""User views"""

import pycountry
from django.db import transaction
from mitol.common.utils import now_in_utc
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.filters import SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from hubspot_sync.task_helpers import sync_hubspot_user
from main.permissions import UserIsOwnerPermission
from main.views import RefinePagination
from openedx import tasks
from users.models import ChangeEmailRequest, User
from users.serializers import (
    ChangeEmailRequestCreateSerializer,
    ChangeEmailRequestUpdateSerializer,
    CountrySerializer,
    PublicUserSerializer,
    StaffDashboardUserSerializer,
    UserSerializer,
)


class UserRetrieveViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """User retrieve viewsets"""

    queryset = User.objects.all()
    serializer_class = PublicUserSerializer
    permission_classes = [IsAuthenticatedOrTokenHasScope, UserIsOwnerPermission]
    required_scopes = ["user"]


class CurrentUserRetrieveUpdateViewSet(
    mixins.UpdateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """User retrieve and update viewsets for the current user"""

    # NOTE: this is a separate viewset from UserRetrieveViewSet because of the differences in permission requirements
    serializer_class = UserSerializer
    permission_classes = []

    def get_object(self):
        """Returns the current request user"""
        # NOTE: this may be a logged in or anonymous user
        return self.request.user

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            user_name = request.user.name
            update_result = super().update(request, *args, **kwargs)
            if user_name != request.data.get("name"):
                tasks.change_edx_user_name_async.delay(request.user.id)
            tasks.update_edx_user_profile.delay(request.user.id)
            sync_hubspot_user(request.user)
            return update_result


class UserInfoViewSet(CurrentUserRetrieveUpdateViewSet):
    """
    User info viewset for the open edx OAuth, extends CurrentUserRetrieveUpdateViewSet
    """

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve the current user's info only if they have an edx_username, otherwise return 409

        This is to prevent issues with Open edX OAuth client that expect an edx_username to be present
        """
        user = self.get_object()
        if user.edx_username:
            return super().retrieve(request, *args, **kwargs)
        return Response(
            {"get": "User has no edx_username."}, status=status.HTTP_409_CONFLICT
        )


class ChangeEmailRequestViewSet(
    mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """Viewset for creating and updating email change requests"""

    lookup_field = "code"

    def get_permissions(self):
        permission_classes = []
        if self.action == "create":
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Return a queryset of valid pending requests"""
        return ChangeEmailRequest.objects.filter(
            expires_on__gt=now_in_utc(), confirmed=False
        )

    def get_serializer_class(self):
        """
        Return the appropriate serializer class based on the action
        """
        if self.action == "create":
            return ChangeEmailRequestCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return ChangeEmailRequestUpdateSerializer
        # Default case
        return ChangeEmailRequestCreateSerializer


class CountriesStatesViewSet(viewsets.GenericViewSet, GenericAPIView):
    """Retrieve viewset of countries, with states/provinces for US and Canada"""

    permission_classes = []
    serializer_class = CountrySerializer

    def get_queryset(self):
        """Get list of countries ordered by name"""
        return sorted(pycountry.countries, key=lambda country: country.name)

    def list(self, request):  # pylint:disable=unused-argument  # noqa: ARG002
        """Get generator for countries/states list"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class UsersViewSet(viewsets.ReadOnlyModelViewSet):
    """Provides an API for listing system users. This is for the staff
    dashboard.
    """

    serializer_class = StaffDashboardUserSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = RefinePagination
    filter_backends = [SearchFilter]
    search_fields = ["username", "name", "email"]
    queryset = User.objects.all()
