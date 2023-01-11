"""User views"""
import pycountry
from django.db import transaction
from django.db.models import Q
from mitol.common.utils import now_in_utc
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework import mixins, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

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
            return update_result


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
        if self.action == "create":
            return ChangeEmailRequestCreateSerializer
        elif self.action == "partial_update":
            return ChangeEmailRequestUpdateSerializer


class CountriesStatesViewSet(viewsets.ViewSet):
    """Retrieve viewset of countries, with states/provinces for US and Canada"""

    permission_classes = []

    def list(self, request):  # pylint:disable=unused-argument
        """Get generator for countries/states list"""
        queryset = sorted(list(pycountry.countries), key=lambda country: country.name)
        serializer = CountrySerializer(queryset, many=True)
        return Response(serializer.data)


class UsersViewSet(viewsets.ReadOnlyModelViewSet):
    """Provides an API for listing system users. This is for the staff
    dashboard."""

    serializer_class = StaffDashboardUserSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = RefinePagination

    def get_queryset(self):
        name_search = self.request.query_params.get("q")

        if name_search is None:
            return User.objects.all()

        return User.objects.filter(
            Q(username__icontains=name_search)
            | Q(name__icontains=name_search)
            | Q(email__icontains=name_search)
        ).all()
