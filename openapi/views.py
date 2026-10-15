"""Views for API documentation"""

import json

from django.conf import settings
from django.urls import reverse
from drf_spectacular.settings import spectacular_settings
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularSwaggerView


class SpectacularSwaggerAllVersionsView(SpectacularSwaggerView):
    """Swagger UI with a dropdown that switches between every version's schema"""

    # Swagger UI ignores the single schema url once `urls` is set; this only
    # keeps the parent's reverse() pointed at a route that exists.
    url_name = "v0_schema"

    @extend_schema(exclude=True)
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        urls = [
            {"url": reverse(f"{version}_schema"), "name": version}
            for version in settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]
        ]
        # drf-spectacular passes a string setting through as raw JS, which is
        # the only way to reference the standalone preset that draws the
        # dropdown (its script is already on the page).
        response.data["settings"] = (
            f"{{...{json.dumps(spectacular_settings.SWAGGER_UI_SETTINGS)},"
            f" urls: {json.dumps(urls)},"
            " presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],"
            ' layout: "StandaloneLayout"}'
        )
        return response
