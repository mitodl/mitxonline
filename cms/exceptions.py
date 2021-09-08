"""Custom exceptions for Wagtail"""

from django.db import DataError


class WagtailSpecificPageError(DataError):
    def __init__(self, spec_page_cls, page_obj, msg=None):
        self.spec_page_cls = spec_page_cls
        self.page_obj = page_obj
        if msg is None:
            msg = (
                "Wagtail data corrupted. A Page object exists (id: {}), but does not have an equivalent "
                "object for the specific page class ({}).\n"
                "Either the Page object(s) need to be manually deleted from the database, or all Wagtail "
                "migrations need re-ran from zero.".format(
                    self.page_obj.id, self.spec_page_cls
                )
            )
        super().__init__(msg)
