from django.urls import include, path

app_name = "v2"

urlpatterns = [
    path("", include("courses.urls.v2.urls")),
]
