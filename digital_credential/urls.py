from django.urls import path

from .views import (
    credential_revoke_view,
    credential_verify_view,
)

urlpatterns = [
    path("revoke/", credential_revoke_view, name="credentials-revoke"),
    path("verify/", credential_verify_view, name="credentials-verify"),
]
