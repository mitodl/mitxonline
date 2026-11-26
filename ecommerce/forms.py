from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from mitol.payment_gateway.constants import STRIPE_PAYMENT_METHOD_TYPES
from mitol.payment_gateway.models import StripePaymentMethodType


class AdminRefundOrderForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.HiddenInput)
    refund_reason = forms.CharField(
        label="Refund reason",
        help_text="The reason for this refund.",
        widget=forms.Textarea(),
        required=True,
    )
    refund_amount = forms.FloatField(
        label="Refund amount", help_text="The amount to be refunded", required=True
    )
    perform_unenrolls = forms.BooleanField(
        label="Unenroll from the purchased course or program", required=False
    )


class StripePaymentMethodTypeAdminForm(forms.ModelForm):
    """
    Admin form for StripePaymentMethodType.

    Edits the Stripe type and ID directly rather than the raw gateway_data, and
    leaves out the gateway field, since the model always saves it as Stripe.
    """

    stripe_type = forms.ChoiceField(
        choices=[(choice, choice.title()) for choice in STRIPE_PAYMENT_METHOD_TYPES],
        help_text=(
            "Custom for a Stripe custom payment method, Builtin for one of Stripe's"
            " own payment methods."
        ),
    )
    stripe_id = forms.CharField(
        max_length=255,
        label="Stripe ID",
        help_text=(
            "The custom payment method type ID (e.g. cpmt_123) for custom methods,"
            " or the Stripe payment method type (e.g. card) for builtin ones."
        ),
    )

    class Meta:
        model = StripePaymentMethodType
        fields = ["name", "stripe_type", "stripe_id", "is_default"]

    def __init__(self, *args, **kwargs):
        """Fill in the Stripe fields from the instance's gateway data."""

        super().__init__(*args, **kwargs)

        if self.instance.pk and isinstance(self.instance.gateway_data, dict):
            self.initial.setdefault("stripe_type", self.instance.stripe_type)
            self.initial.setdefault("stripe_id", self.instance.stripe_id)

    def clean_name(self):
        """
        Make sure the name is unique among Stripe payment methods.

        The unique constraint includes the gateway field, which isn't on this
        form, so Django won't check it for us.
        """

        name = self.cleaned_data["name"]
        duplicates = StripePaymentMethodType.objects.filter(name=name).exclude(
            pk=self.instance.pk
        )
        if duplicates.exists():
            msg = "A Stripe payment method with this name already exists."
            raise ValidationError(msg)

        return name

    def _post_clean(self):
        """Copy the Stripe fields onto the instance before the model validates it."""

        if not isinstance(self.instance.gateway_data, dict):
            self.instance.gateway_data = {}

        if "stripe_type" in self.cleaned_data:
            self.instance.stripe_type = self.cleaned_data["stripe_type"]
        if "stripe_id" in self.cleaned_data:
            self.instance.stripe_id = self.cleaned_data["stripe_id"]

        super()._post_clean()

    def _update_errors(self, errors):
        """
        Show the model's gateway_data errors as form-wide errors.

        gateway_data isn't a field on this form, so Django would raise a
        ValueError if we passed those errors through unchanged.
        """

        if hasattr(errors, "error_dict") and "gateway_data" in errors.error_dict:
            error_dict = dict(errors.error_dict)
            gateway_errors = error_dict.pop("gateway_data")
            error_dict[NON_FIELD_ERRORS] = [
                *error_dict.get(NON_FIELD_ERRORS, []),
                *gateway_errors,
            ]
            errors = ValidationError(error_dict)

        super()._update_errors(errors)
