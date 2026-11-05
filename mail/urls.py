"""URL configurations for mail"""

from django.conf import settings
from django.urls import path

from mail.views import EmailDebuggerView

urlpatterns = []

if settings.DEBUG and settings.MITOL_MAIL_ENABLE_EMAIL_DEBUGGER:
    # By default, this collides with the mitol.mail.urls path.
    # Ideally we'd use one across the board, but for now we'll just allow folks to access both
    # since they have different templates.
    urlpatterns += [
        path("__maildebugger__/", EmailDebuggerView.as_view(), name="email-debugger")
    ]
