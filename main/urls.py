"""project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from oauth2_provider.urls import base_urlpatterns, oidc_urlpatterns
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from cms.views import instructor_page
from cms.wagtail_api.urls import api_router as wagtail_api_router
from main.views import (
    cms_signin_redirect_to_site_signin,
    index,
    refine,
    staff_dashboard_signin_redirect_to_site_signin,
)

urlpatterns = [
    # NOTE: we only bring in base_urlpatterns so applications can only be created via django-admin
    path(
        "oauth2/",
        include(
            (base_urlpatterns + oidc_urlpatterns, "oauth2_provider"),
            namespace="oauth2_provider",
        ),
    ),
    path("admin/", admin.site.urls),
    path("hijack/", include("hijack.urls")),
    path("robots.txt", include("robots.urls")),
    re_path(r"^api/schema/$", SpectacularAPIView.as_view(), name="schema"),
    re_path(
        r"^api/schema/swagger-ui/$",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger",
    ),
    path("", include("authentication.urls")),
    path("", include("openedx.urls")),
    path("", include("mail.urls")),
    path("", include("users.urls")),
    path("", include("courses.urls")),
    path("", include("ecommerce.urls")),
    path("", include("flexiblepricing.urls")),
    path("", include("mitol.google_sheets.urls")),
    path("", include("b2b.urls")),
    re_path(r"", include("mitol.scim.urls")),
    re_path(r"^dashboard/", index, name="user-dashboard"),
    # Staff dashboard authentication redirect
    re_path(
        r"^staff-dashboard/$",
        staff_dashboard_signin_redirect_to_site_signin,
        name="staff-dashboard-login",
    ),
    re_path(r"^staff-dashboard/.*", refine, name="staff-dashboard"),
    path("create-account/", index, name="signup"),
    path("create-account/confirm-sent/", index, name="confirm-sent"),
    path("create-account/details/", index, name="signup-details"),
    path("create-profile/", index, name="profile-details"),
    path("create-profile-extra/", index, name="profile-details-extra"),
    path("create-account/additional-details/", index, name="signup-addl-details"),
    path("create-account/denied/", index, name="signup-denied"),
    path("create-account/error/", index, name="signup-error"),
    path("create-account/confirm/", index, name="register-confirm"),
    path("account/inactive/", index, name="account-inactive"),
    path("account/confirm-email/", index, name="account-confirm-email-change"),
    path("profile/", index, name="view-profile"),
    path("profile/edit/", index, name="edit-profile"),
    re_path(r"^account-settings/", index, name="account-settings"),
    re_path(r"^cart/.*", index, name="cart"),
    re_path(r"^orders/history/.*", index, name="order-history"),
    re_path(r"^orders/receipt/.*", index, name="order-receipt"),
    re_path(r"^records/.*", index, name="learner-records"),
    re_path(r"^catalog/", index, name="catalog"),
    path("api/instructor/<int:id>/", instructor_page, name="cms_instructor_page"),
    re_path(r"^health/", include("health_check.urls")),
    # Wagtail
    re_path(
        r"^cms/login", cms_signin_redirect_to_site_signin, name="wagtailadmin_login"
    ),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("api/v2/", wagtail_api_router.urls),
    path("", include(wagtail_urls)),
    path("", include("cms.urls")),
    # Example view
    path("", index, name="main-index"),
] + (
    static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
)

handler500 = "main.views.handler500"
handler404 = "main.views.handler404"

if settings.DEBUG:
    import debug_toolbar  # pylint: disable=wrong-import-position, wrong-import-order

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
