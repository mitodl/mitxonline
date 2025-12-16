from django.urls import path

from .views import (
    CredentialPresentView,
    CredentialRevokeView,
    CredentialVerifyView,
)

urlpatterns = [
    path("present/<str:credential_id>", CredentialPresentView.as_view(), name="credentials-present"),
    path("revoke/", CredentialRevokeView.as_view(), name="credentials-revoke"),
    path("verify/", CredentialVerifyView.as_view(), name="credentials-verify"),
]
