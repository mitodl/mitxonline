"""
Serializers for Wagtail API
"""

from rest_framework import serializers
from rest_framework.fields import Field
from wagtail.api.v2.serializers import get_serializer_class
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.images.models import Image
from wagtail.models import Page


class ImageSerializer(serializers.ModelSerializer):
    """
    Serializer for Wagtail Image model.
    """

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = [
            "title",
            "image_url",
            "height",
            "width",
        ]

    def get_image_url(self, obj):
        if obj:
            return obj.file.url
        return None


class ProductChildPageSerializer(Field):
    """
    Serializer Field for related ChildPage objects
    """

    def to_representation(self, value):
        """
        Serializes a queryset of page instances.
        Returns a list of serialized page instances.
        """
        if hasattr(value, "all"):
            base_context = {"view": PagesAPIViewSet()}
            context = {**base_context, **getattr(self, "context", {})}
            return [self.serialize_page(page, context) for page in value.all()]
        return self.serialize_page(value, self.context)

    def serialize_page(self, page, context):
        """
        Serializes a single page instance.
        """
        if not isinstance(page, Page):
            return None

        model = page.specific.__class__

        body_fields = PagesAPIViewSet.get_body_fields_names(model)
        meta_fields = PagesAPIViewSet.get_meta_fields_names(model)
        all_fields = body_fields + meta_fields

        serializer = get_serializer_class(
            model,
            all_fields,
            meta_fields,
            base=PagesAPIViewSet.base_serializer_class,
        )

        return serializer(page.specific, context=context).data
