"""Google Sheets integration code for B2B."""

import logging

from django.utils.functional import cached_property
from mitol.google_sheets.api import get_authorized_pygsheets_client
from mitol.google_sheets.constants import GOOGLE_SHEET_FIRST_ROW
from mitol.google_sheets.sheet_handler_api import SheetHandler

from b2b.models import ContractPage

log = logging.getLogger(__name__)


class ContractEnrollmentCodesSheetHandler(SheetHandler):
    """Sends enrollment code data to a specified Google Sheet"""

    default_columns = [
        "Enrollment Code",
        "Use Type",
        "Total Redemptions",
        "Invalidated On",
        "Redeemed By",
        "Redeemed On",
    ]

    def __init__(
        self,
        spreadsheet_url: str,
        worksheet_name: str | int,
        *,
        start_row: int | None = 0,
    ):
        """
        Initialize the class.

        Unlike the deferrals and refunds code, this expects a spreadsheet URL. It
        expects to have to work on a number of different sheets that are created
        by a number of potentially non-technical people so it seems easier to
        accept a URL.

        Args:
            spreadsheet_url (str): the spreadsheet to use
            worksheet_name (str|int): the worksheet (tab) name or index to use
            start_row (int): starting row (optional, starts at 0)
            sheet_metadata (Type(SheetConfig)):
            request_model_cls (Type(GoogleSheetsRequestModel)):
        """
        self.pygsheets_client = get_authorized_pygsheets_client()
        self.spreadsheet = self.pygsheets_client.open_by_url(spreadsheet_url)
        self.worksheet_name = worksheet_name
        self.start_row = start_row

    @cached_property
    def worksheet(self):
        """Return the specified worksheet"""

        return self.spreadsheet.worksheet(
            property="index" if isinstance(self.worksheet_name, int) else "title",
            value=self.worksheet_name,
        )

    @property
    def row_zero(self):
        """Gets the first row we're supposed to use."""

        return GOOGLE_SHEET_FIRST_ROW + self.start_row

    @property
    def row_one(self):
        """Gets the first row for data, based on row_zero."""

        return self.row_zero + 1

    def _write_header(self):
        """Write/overwrite the header row."""

        self.worksheet.update_row(self.row_zero, self.default_columns)

    def ensure_header(self):
        """Ensure there's a header row in the worksheet."""

        header_row_values = self.worksheet.get_row(self.row_zero)

        if len(header_row_values) == 0:
            self._write_header()
            return

        for idx, rowvalue in enumerate(header_row_values):
            if rowvalue != self.default_columns[idx]:
                self._write_header()
                return

    def write_codes(self, contract: ContractPage):
        """
        Write out all the enrollment codes for the contract.

        As with the b2b_codes command, this will just write out the codes that
        are necessary to fill out the contract. No provision for getting _all_
        the codes. Use the command for that if you need it.
        """

        return

    def check_code(self, enrollment_code: str):
        """Check for the given enrollment code in the sheet."""

        return enrollment_code

    def update_code(self, enrollment_code: str):
        """
        Update the enrollment code in the sheet.

        There are some status columns in the worksheet - Invalidated On, Total
        Redemptions, Redeemed By, and Redeemed On. This fills those values for
        the code.
        """

        return enrollment_code
