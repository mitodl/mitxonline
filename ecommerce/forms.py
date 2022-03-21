from django import forms


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
        label="Unenroll from the purchased course", required=False
    )
