"""MITx Online serializers"""

from django.conf import settings
from rest_framework import serializers


class AppContextSerializer(serializers.Serializer):
    """Serializer for the application context"""

    gtm_tracking_id = serializers.SerializerMethodField()
    ga_tracking_id = serializers.SerializerMethodField()
    environment = serializers.SerializerMethodField()
    release_version = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()

    def get_features(self, request):  # noqa: ARG002
        """Returns a dictionary of features"""
        return {}

    def get_release_version(self, request):  # noqa: ARG002
        """Returns a dictionary of features"""
        return settings.VERSION

    def get_gtm_tracking_id(self, request):  # noqa: ARG002
        """Returns the GTM container ID"""
        return settings.GTM_TRACKING_ID

    def get_ga_tracking_id(self, request):  # noqa: ARG002
        """Returns a dictionary of features"""
        return settings.GA_TRACKING_ID

    def get_environment(self, request):  # noqa: ARG002
        """Returns a dictionary of features"""
        return settings.ENVIRONMENT


class WriteableSerializerMethodField(serializers.SerializerMethodField):
    """
    A SerializerMethodField which has been marked as not read_only so that submitted data passed validation.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.read_only = False

    def to_internal_value(self, data):
        return data


class StrictFieldsSerializer(serializers.Serializer):
    """A serializer that validates that only fields defined on the serializer are used"""

    def validate(self, data):
        """
        Validate that the only fields that are being passed are the ones defined by the serializer
        """
        data = super().validate(data)

        # because we allow the data to be serialized right into the database
        # we need to ensure there are no fields being passed that we haven't specified above
        if hasattr(self, "initial_data"):
            unknown_keys = set(self.initial_data.keys()) - set(self.fields.keys())
            if unknown_keys:
                raise ValidationError({key: "Invalid field" for key in unknown_keys})  # noqa: F821

        return data
