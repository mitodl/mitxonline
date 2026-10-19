"""
Custom forms for the cms
"""

from wagtail.admin.forms import WagtailAdminPageForm


class CertificatePageForm(WagtailAdminPageForm):
    """
    Custom form for CertificatePage in order to filter course run IDs
    """

    # pylint: disable=keyword-arg-before-vararg
    def __init__(self, data=None, files=None, parent_page=None, *args, **kwargs):
        super().__init__(data, files, parent_page, *args, **kwargs)
        if parent_page.specific.is_course_page:
            self.fields["overrides"].block.child_blocks["course_run"].child_blocks[
                "readable_id"
            ].parent_readable_id = parent_page.specific.course.readable_id

    def clean(self):
        cleaned_data = super().clean()

        provisioning_enabled = cleaned_data["should_provision_verifiable_credential"]
        criteria = cleaned_data["verifiable_credential_criteria"]
        if provisioning_enabled and not criteria:
            self.add_error(
                "verifiable_credential_criteria",
                "You must specify criteria if provisioning is enabled",
            )

        return cleaned_data
