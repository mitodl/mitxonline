"""
Custom URLs for serving Wagtail pages

NOTE:
These definitions are needed because we want to serve pages at URLs that match
edX course ids, and those edX course ids contain characters that do not match Wagtail's
expected URL pattern (https://github.com/wagtail/wagtail/blob/a657a75/wagtail/core/urls.py)

Example: "course-v1:edX+DemoX+Demo_Course" – Wagtail's pattern does not match the ":" or
the "+" characters.

The pattern(s) defined here serve the same Wagtail view that the library-defined pattern serves.
"""  # noqa: RUF002

from django.urls import include, path, re_path
from wagtail import urls as wagtail_urls
from wagtail import views
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.coreutils import WAGTAIL_APPEND_SLASH
from wagtail.documents import urls as wagtaildocs_urls

from cms.constants import COURSE_INDEX_SLUG, PROGRAM_INDEX_SLUG

detail_path_char_pattern = r"\w\-\.+:"

app_name = "cms"

if WAGTAIL_APPEND_SLASH:
    custom_serve_pattern = (
        rf"^({COURSE_INDEX_SLUG}/(?:[{detail_path_char_pattern}]+/)*)$"
    )

    program_custom_serve_pattern = (
        rf"^({PROGRAM_INDEX_SLUG}/(?:[{detail_path_char_pattern}]+/)*)$"
    )
else:
    custom_serve_pattern = rf"^({COURSE_INDEX_SLUG}/[{detail_path_char_pattern}/]*)$"
    program_custom_serve_pattern = (
        rf"^({PROGRAM_INDEX_SLUG}/[{detail_path_char_pattern}/]*)$"
    )


urlpatterns = [
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("", include(wagtail_urls)),
    re_path(custom_serve_pattern, views.serve, name="wagtail_serve_custom"),
    re_path(program_custom_serve_pattern, views.serve, name="wagtail_serve_custom"),
]
