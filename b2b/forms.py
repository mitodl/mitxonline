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

        The change is measured against the stored contract and its latest
        draft, not against the object the form is bound to. On a revert
        Wagtail binds the form to the old revision, so the form's own idea of
        what changed would restore an opt-in along with the stamp of whoever
        recorded it the first time.
        """

        contract = self.instance
        stored = (
            type(contract).objects.filter(pk=contract.pk).first()
            if contract.pk
            else None
        )
        opted_in = self.cleaned_data["learner_records_opt_in"]

        # The stored row first: a draft that ends up where the live contract
        # already is hasn't changed anything. Then the latest draft, so a
        # change saved as a draft keeps its stamp through later edits to
        # other fields, by whoever makes them.
        unchanged_from = None
        if stored:
            latest_draft = stored.get_latest_revision_as_object()
            if opted_in == stored.learner_records_opt_in:
                unchanged_from = stored
            elif opted_in == latest_draft.learner_records_opt_in:
                unchanged_from = latest_draft

        if unchanged_from:
            contract.learner_records_opt_in_recorded_on = (
                unchanged_from.learner_records_opt_in_recorded_on
            )
            contract.learner_records_opt_in_recorded_by_id = (
                unchanged_from.learner_records_opt_in_recorded_by_id
            )
        elif opted_in or stored:
            contract.learner_records_opt_in_recorded_on = now_in_utc()
            contract.learner_records_opt_in_recorded_by = self.for_user
        else:
            # A new contract that isn't opted in has nothing to record.
            contract.learner_records_opt_in_recorded_on = None
            contract.learner_records_opt_in_recorded_by = None

        return super().save(commit=commit)
