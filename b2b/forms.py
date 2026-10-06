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

        The change is measured against the stored contract, not against the
        object the form is bound to. Wagtail binds the form to the latest
        draft, or to an old revision on a revert, so the form's own idea of
        what changed would let a revert restore an opt-in along with the
        stamp of whoever recorded it the first time.
        """

        contract = self.instance
        stored = (
            type(contract)
            .objects.filter(pk=contract.pk)
            .values(
                "learner_records_opt_in",
                "learner_records_opt_in_recorded_on",
                "learner_records_opt_in_recorded_by_id",
            )
            .first()
            if contract.pk
            else None
        )

        was_opted_in = stored["learner_records_opt_in"] if stored else False
        if self.cleaned_data["learner_records_opt_in"] != was_opted_in:
            contract.learner_records_opt_in_recorded_on = now_in_utc()
            contract.learner_records_opt_in_recorded_by = self.for_user
        else:
            contract.learner_records_opt_in_recorded_on = (
                stored["learner_records_opt_in_recorded_on"] if stored else None
            )
            contract.learner_records_opt_in_recorded_by_id = (
                stored["learner_records_opt_in_recorded_by_id"] if stored else None
            )

        return super().save(commit=commit)
