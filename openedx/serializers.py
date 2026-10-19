"""Serializers for the openedx app"""

from rest_framework import serializers

NOTIFICATION_CHANNELS = ("web", "push", "email", "email_cadence")
EMAIL_CADENCES = ("Daily", "Weekly", "Immediately")


class NotificationPreferenceUpdateSerializer(serializers.Serializer):
    """
    Validates one field-level notification preference change.

    The upstream Open edX API updates a single channel per request, so each
    toggle or cadence change is its own payload. Validating locally keeps a
    malformed change from spending one of the learner's LMS rate-limited
    requests, and gives the frontend a useful 400 instead of a 502.
    """

    notification_app = serializers.CharField()
    notification_type = serializers.CharField()
    notification_channel = serializers.ChoiceField(choices=NOTIFICATION_CHANNELS)
    value = serializers.BooleanField(required=False)
    email_cadence = serializers.ChoiceField(choices=EMAIL_CADENCES, required=False)

    def validate(self, attrs):
        """Require the payload field that matches the channel being changed"""
        if attrs["notification_channel"] == "email_cadence":
            if "email_cadence" not in attrs:
                raise serializers.ValidationError(
                    {
                        "email_cadence": "This field is required when changing the email cadence."
                    }
                )
        elif "value" not in attrs:
            raise serializers.ValidationError(
                {"value": "This field is required when changing a boolean channel."}
            )
        return attrs
