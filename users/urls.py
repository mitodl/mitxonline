"""User url routes"""

from django.urls import include, path
from rest_framework import routers

from users.new_views import (
    CurrentUserRetrieveUpdateViewSet as NewCurrentUserRetrieveUpdateViewSet,
)
from users.views import (
    ChangeEmailRequestViewSet,
    CountriesStatesViewSet,
    CurrentUserRetrieveUpdateViewSet,
    UserInfoViewSet,
    UserRetrieveViewSet,
    UsersViewSet,
)

router = routers.DefaultRouter()
router.register(r"users", UserRetrieveViewSet, basename="users_api")
router.register(r"countries", CountriesStatesViewSet, basename="countries_api")
router.register(
    r"change-emails", ChangeEmailRequestViewSet, basename="change_email_api"
)
router.register(r"user_search", UsersViewSet, basename="users_search_api")

urlpatterns = [
    path("api/", include(router.urls)),
    path(
        "api/users/me",
        CurrentUserRetrieveUpdateViewSet.as_view(
            {"patch": "update", "get": "retrieve"}
        ),
        name="users_api-me",
    ),
    path(
        "api/v0/users/me",
        CurrentUserRetrieveUpdateViewSet.as_view(
            {"patch": "update", "get": "retrieve"}
        ),
        name="users_api-me",
    ),
    path(
        "api/v0/users/current_user/",
        NewCurrentUserRetrieveUpdateViewSet.as_view(
            {"patch": "update", "get": "retrieve"}
        ),
        name="users_api-current_user",
    ),
    path(
        "api/v0/userinfo/",
        UserInfoViewSet.as_view({"get": "retrieve"}),
        name="userinfo_api",
    ),
    path("api/v0/", include(router.urls)),
]
