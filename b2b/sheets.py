"""Google Sheets integration code for B2B."""

import logging

from django.utils.functional import cached_property
from mitol.google_sheets.api import get_authorized_pygsheets_client
from mitol.google_sheets.constants import GOOGLE_SHEET_FIRST_ROW
from mitol.google_sheets.sheet_handler_api import SheetHandler

from b2b.constants import CONTRACT_MEMBERSHIP_AUTOS
from b2b.models import ContractPage
from ecommerce.constants import REDEMPTION_TYPE_UNLIMITED
from ecommerce.models import Discount

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
        contract_page: ContractPage,
    ):
        """
        Initialize the class.

        This uses the same base as the deferrals and refunds handling code,
        but it splits from it a lot. This expects a GSheets URL rather than an
        ID, and it expects those to come from the ContractPage, because we allow
        for each contract to have its own page. Same with the sheet tab.

        This will also raise a ValueError if you pass in a ContractPage that does
        not have enrollment codes.

        Args:
            contract_page (ContractPage): the contract to work with
        """

        if not contract_page.google_sheet_target:
            msg = f"Contract {contract_page} has no linked Google Sheet, can't continue"
            raise ValueError(msg)

        if contract_page.membership_type in CONTRACT_MEMBERSHIP_AUTOS:
            msg = f"Membership for contract {contract_page} is managed; no enrollment codes, so can't continue"
            raise ValueError(msg)

        self.contract_page = contract_page
        self.pygsheets_client = get_authorized_pygsheets_client()
        self.spreadsheet = self.pygsheets_client.open_by_url(
            contract_page.google_sheet_target
        )
        self.worksheet_name = contract_page.google_sheet_target_tab
        self.start_row = 0  # unimplemented at this point

    @cached_property
    def worksheet(self):
        """Return the specified worksheet"""

        return self.spreadsheet.worksheet(
            property="index" if isinstance(self.worksheet_name, int) else "title",
            value=self.worksheet_name,
        )

    @property
    def row_zero(self) -> int:
        """Gets the first row we're supposed to use."""

        return GOOGLE_SHEET_FIRST_ROW + self.start_row

    @property
    def row_one(self) -> int:
        """Gets the first row for data, based on row_zero."""

        return self.row_zero + 1

    def _write_header(self):
        """Write/overwrite the header row."""

        self.worksheet.update_row(self.row_zero, self.default_columns)

    def _get_discount_cells(self, discount: Discount) -> list:
        """Format the discount for the sheet"""

        redemption_date = ""
        redeemed_by = ""
        redeemed_on = ""

        if (
            discount.redemption_type != REDEMPTION_TYPE_UNLIMITED
            and discount.contract_redemptions.count() > 0
        ):
            redemption_date = str(discount.contract_redemptions.get().created_on)

        if discount.contract_redemptions.exists():
            redeemed_by = discount.contract_redemptions.last().user.email
            redeemed_on = str(discount.contract_redemptions.last().created_on)

        return [
            discount.discount_code,
            discount.redemption_type,
            discount.contract_redemptions.count(),
            str(discount.expiration_date)
            if discount.expiration_date
            else redemption_date,
            redeemed_by,
            redeemed_on,
        ]

    def ensure_header(self):
        """Ensure there's a header row in the worksheet."""

        header_row_values = self.worksheet.get_row(self.row_zero)

        if len(header_row_values) == 0:
            self._write_header()
            return

        for idx, rowvalue in enumerate(header_row_values):
            if idx >= len(self.default_columns):
                break

            if rowvalue != self.default_columns[idx]:
                self._write_header()
                return

    def write_codes(self) -> int:
        """
        Write out all the enrollment codes for the contract.

        As with the b2b_codes command, this will just write out the codes that
        are necessary to fill out the contract. No provision for getting _all_
        the codes. Use the command for that if you need it.
        """

        self.ensure_header()

        row_idx = self.row_one
        codes = []

        for code in self.contract_page.discounts_qs.prefetch_related(
            "contract_redemptions", "contract_redemptions__user"
        ).all()[: self.contract_page.max_learners]:
            col = self._get_discount_cells(code)

            code.b2b_sheet_location = row_idx
            codes.append(code)

            self.worksheet.update_row(row_idx, col)

            row_idx += 1

        Discount.objects.bulk_update(codes, {"b2b_sheet_location"})

        return row_idx - self.row_one

    def check_code(self, enrollment_code: str) -> int:
        """Check for the given enrollment code in the sheet."""

        discount = self.contract_page.discounts_qs.filter(
            discount_code=enrollment_code
        ).get()

        if discount.b2b_sheet_location:
            cached_row = self.worksheet.get_row(
                discount.b2b_sheet_location, tailing_empty=False, returnas="matrix"
            )

            if cached_row[0] == discount.discount_code:
                return discount.b2b_sheet_location

        found_cell = self.worksheet.find(
            discount.discount_code,
            matchEntireCell=True,
            rows=(self.row_one, None),
            cols=(1, 1),
        )

        if len(found_cell) == 0:
            return False

        if len(found_cell) > 1:
            found_locs = ",".join([f"({cell.row},{cell.col})" for cell in found_cell])
            msg = f"Code {discount.discount_code} seems to be in the sheet more than once: {found_locs}"

            raise ValueError(msg)

        discount.b2b_sheet_location = found_cell[0].row
        discount.b2b_sheet_location.save()

        return found_cell[0].row

    def update_code(self, enrollment_code: str):
        """
        Update the enrollment code in the sheet.

        There are some status columns in the worksheet - Invalidated On, Total
        Redemptions, Redeemed By, and Redeemed On. This fills those values for
        the code.
        """

        discount = self.contract_page.discounts_qs.filter(
            discount_code=enrollment_code
        ).get()

        row = self.check_code(enrollment_code)

        update_col = self._get_discount_cells(discount)

        self.worksheet.update_row(row, update_col)
