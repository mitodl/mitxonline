"""Wagtail admin forms for B2B pages."""

from mitol.common.utils import now_in_utc
from wagtail.admin.forms import WagtailAdminPageForm


class ContractPageForm(WagtailAdminPageForm):
    """Stamp who changed a contract's learner records opt-in, and when."""

    def save(self, commit=True):  # noqa: FBT002
        """
        Record the editor and time when the opt-in changes in either direction.

        This is done here, not in ContractPage.save, because the form is the
        only place the editing user is known: Wagtail publishes a live page
        from its revision without passing the user to save.
        """

        if "learner_records_opt_in" in self.changed_data:
            self.instance.learner_records_opt_in_recorded_on = now_in_utc()
            self.instance.learner_records_opt_in_recorded_by = self.for_user

        return super().save(commit=commit)
