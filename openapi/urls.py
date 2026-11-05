"""
URL Configuration for schema & documentation views
"""

from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from main.versioning import NoVersioning
from openapi.views import SpectacularSwaggerAllVersionsView

urlpatterns = [
    path(
        "api/v0/schema/",
        SpectacularAPIView.as_view(api_version="v0", versioning_class=NoVersioning),
        name="v0_schema",
    ),
    path(
        "api/v0/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(
            url_name="v0_schema", versioning_class=NoVersioning
        ),
        name="v0_swagger_ui",
    ),
    path(
        "api/v0/schema/redoc/",
        SpectacularRedocView.as_view(
            url_name="v0_schema", versioning_class=NoVersioning
        ),
        name="v0_redoc",
    ),
    path(
        "api/v1/schema/",
        SpectacularAPIView.as_view(api_version="v1", versioning_class=NoVersioning),
        name="v1_schema",
    ),
    path(
        "api/v1/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(
            url_name="v1_schema", versioning_class=NoVersioning
        ),
        name="v1_swagger_ui",
    ),
    path(
        "api/v1/schema/redoc/",
        SpectacularRedocView.as_view(
            url_name="v1_schema", versioning_class=NoVersioning
        ),
        name="v1_redoc",
    ),
    path(
        "api/v2/schema/",
        SpectacularAPIView.as_view(api_version="v2", versioning_class=NoVersioning),
        name="v2_schema",
    ),
    path(
        "api/v2/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(
            url_name="v2_schema", versioning_class=NoVersioning
        ),
        name="v2_swagger_ui",
    ),
    path(
        "api/v2/schema/redoc/",
        SpectacularRedocView.as_view(
            url_name="v2_schema", versioning_class=NoVersioning
        ),
        name="v2_redoc",
    ),
    path(
        "api/v3/schema/",
        SpectacularAPIView.as_view(api_version="v3", versioning_class=NoVersioning),
        name="v3_schema",
    ),
    path(
        "api/v3/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(
            url_name="v3_schema", versioning_class=NoVersioning
        ),
        name="v3_swagger_ui",
    ),
    path(
        "api/v3/schema/redoc/",
        SpectacularRedocView.as_view(
            url_name="v3_schema", versioning_class=NoVersioning
        ),
        name="v3_redoc",
    ),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerAllVersionsView.as_view(versioning_class=NoVersioning),
        name="swagger_ui",
    ),
]
