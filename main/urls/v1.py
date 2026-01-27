from django.urls import include, path

app_name = "v1"

urlpatterns = [path("", include("courses.urls.v1.urls"))]
