from django.urls import include, path

from cms.wagtail_api.router import api_router

app_name = "v2"

urlpatterns = [
    path("", include("courses.urls.v2.urls")),
    path("", api_router.urls),
]
