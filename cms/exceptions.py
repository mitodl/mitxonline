"""Custom exceptions for Wagtail"""

from django.db import DataError


class WagtailSpecificPageError(DataError):
    def __init__(self, spec_page_cls, page_obj, msg=None):
        self.spec_page_cls = spec_page_cls
        self.page_obj = page_obj
        if msg is None:
            msg = (
                f"Wagtail data corrupted. A Page object exists (id: {self.page_obj.id}), but does not have an equivalent "
                f"object for the specific page class ({self.spec_page_cls}).\n"
                "Either the Page object(s) need to be manually deleted from the database, or all Wagtail "
                "migrations need re-ran from zero."
            )
        super().__init__(msg)
