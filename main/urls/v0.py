from django.urls import include, path

app_name = "v0"

urlpatterns = [
    path("b2b/", include("b2b.views.v0.urls")),
    path("", include("ecommerce.views.v0.urls")),
]
