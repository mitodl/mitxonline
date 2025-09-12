from django.forms.models import ModelForm


class OpenEdxUserForm(ModelForm):
    """Custom form for the openedx user"""

    def clean(self):
        cleaned_data = super().clean()

        cleaned_data["desired_edx_username"] = cleaned_data["edx_username"]

        return cleaned_data
