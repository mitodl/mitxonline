from django.db.models import QuerySet


def extend_schema_get_queryset(queryset: QuerySet):
    """
    DRF Spectacular uses a ViewSet's queryset to generate parts of the schema
    (for example, the type of the primary key).

    If the queryset cannot be determined at schema generation time (e.g., it
    requires an authenticated user) then this can be used to specify the
    queryset.

    See https://drf-spectacular.readthedocs.io/en/latest/faq.html#my-get-queryset-depends-on-some-attributes-not-available-at-schema-generation-time
    for more information.
    """

    def decorate(get_queryset):
        def decorated(self, *args, **kwargs):
            if getattr(self, "swagger_fake_view", False):  # drf-yasg comp
                return queryset
            return get_queryset(self, *args, **kwargs)

        return decorated

    return decorate
