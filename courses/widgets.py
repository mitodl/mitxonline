"""Widgets for course forms"""

from django.forms.widgets import TextInput


class ProgramRequirementsInput(TextInput):
    """
    This class implements a UI for program requirements
    """

    template_name = "forms/widgets/program-requirements-input.html"

    def __init__(self, *args, **kwargs):
        self.schema = kwargs.pop("schema", None)
        super().__init__(*args, **kwargs)

    def _get_schema(self):
        return self.schema() if callable(self.schema) else self.schema

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["schema"] = self._get_schema()
        return context
