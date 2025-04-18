"""MITx Online serializers"""

from rest_framework import serializers


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
