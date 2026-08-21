"""Widgets for course forms"""

from django.forms.widgets import TextInput


class ProgramRequirementsInput(TextInput):
    """
    This class implements a UI for program requirements
    """

    template_name = "forms/widgets/program-requirements-input.html"

    def __init__(self, *args, **kwargs):
        self.catalog = kwargs.pop("catalog", None)
        super().__init__(*args, **kwargs)

    def _get_catalog(self):
        return self.catalog() if callable(self.catalog) else self.catalog

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["catalog"] = self._get_catalog()
        return context
