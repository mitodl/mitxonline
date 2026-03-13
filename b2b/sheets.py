"""Google Sheets integration code for B2B."""

import logging

from django.db.models import Count
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
        self.last_blank_row = 0

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

    def _get_sorted_codes(self):
        """
        Return the applicable discount codes for the contract.

        Like the b2b_codes command, this limits output to the codes necessary to
        fill the contract. Unlike the b2b_codes command, we also want to get the
        codes that have been used, so this adds an annotation so we can sort by
        contract redemption.
        """

        return (
            self.contract_page.discounts_qs.prefetch_related(
                "contract_redemptions", "contract_redemptions__user"
            )
            .annotate(attach_redemption_count=Count("contract_redemptions"))
            .all()
            .order_by("-attach_redemption_count", "id")[
                : self.contract_page.max_learners
            ]
        )

    def _write_row(self, row: int, columns: list) -> int:
        """
        Write the row to the current worksheet at the specified location.

        If row is set to a negative, then we will use the first blank line in
        the sheet that we can find. This will cache the last blank row found, so
        future calls should start from there rather than having to scan the
        entire sheet each time.
        """

        if row < 0:
            # Now we have to figure out where the next blank column is.
            found_blank = False
            search_idx = self.last_blank_row
            empty_cols = ["" for col in self.default_columns]
            while not found_blank:
                cells = self.worksheet.get_row(self.row_one + search_idx)

                if len(cells) == 0 or cells[: len(self.default_columns)] == empty_cols:
                    found_blank = True
                    break

                search_idx += 1

            row = search_idx + self.row_one - 1  # GSheets is 1-indexed
            self.last_blank_row = search_idx

        self.worksheet.update_row(row, columns)

        return row

    def _write_header(self):
        """Write/overwrite the header row."""

        self._write_row(self.row_zero, self.default_columns)

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

        if len(header_row_values) != 0:
            log.warning(
                "ContractEnrollmentCodeSheetHandler.ensure_header: header row for sheet %s in contract %s has data in it that we're now going to overwrite.",
                self.worksheet_name,
                self.contract_page,
            )

        self._write_header()

    def write_codes(self) -> int:
        """
        Write out all the enrollment codes for the contract.

        See notes in _get_sorted_codes - but this will write out all the used
        and unused codes for the contract, until it has written enough codes to
        complete the contract (hits max_learners).

        This function is destructive so use "update_codes" if the sheet has been
        modified.
        """

        self.ensure_header()

        row_idx = self.row_one
        codes = []

        for code in self._get_sorted_codes():
            col = self._get_discount_cells(code)

            code.b2b_sheet_location = row_idx
            codes.append(code)

            self._write_row(row_idx, col)

            row_idx += 1

        Discount.objects.bulk_update(codes, {"b2b_sheet_location"})

        return row_idx - self.row_one

    def check_code(self, discount: Discount, *, no_update: bool = False) -> int:
        """Check for the given enrollment code in the sheet."""

        if discount.b2b_sheet_location and int(discount.b2b_sheet_location) > 0:
            cached_row = self.worksheet.get_row(
                int(discount.b2b_sheet_location),
                include_tailing_empty=False,
                returnas="matrix",
            )

            if cached_row and cached_row[0] == discount.discount_code:
                return int(discount.b2b_sheet_location)

        found_cell = self.worksheet.find(
            discount.discount_code,
            matchEntireCell=True,
            rows=(self.row_one, None),
            cols=(1, 1),
        )

        if len(found_cell) == 0:
            return -1

        if len(found_cell) > 1:
            found_locs = ",".join([f"({cell.row},{cell.col})" for cell in found_cell])
            msg = f"Code {discount.discount_code} seems to be in the sheet more than once: {found_locs}"

            raise ValueError(msg)

        if not no_update:
            discount.b2b_sheet_location = found_cell[0].row
            discount.save()

        return found_cell[0].row

    def update_code(self, discount: Discount, *, no_update: bool = False) -> int:
        """
        Update the enrollment code in the sheet.

        There are some status columns in the worksheet - Invalidated On, Total
        Redemptions, Redeemed By, and Redeemed On. This fills those values for
        the code if the code is in the sheet already. If it isn't, then it'll
        be appended.
        """

        row = self.check_code(discount, no_update=no_update)

        update_col = self._get_discount_cells(discount)

        return self._write_row(row, update_col)

    def update_sheet(self) -> int:
        """
        Update the entire sheet, preserving codes in their locations.

        The write_codes function will destructively write and prepare the sheet.
        This isn't good if we've given the customer the sheet, because they will
        probably edit it. So, when we need to refresh the entire sheet, we need
        to take care to not move the codes around so we don't muck up any of the
        data the customer's put into the sheet.
        """

        row_idx = self.row_one
        codes = []

        for code in self._get_sorted_codes():
            row = self.update_code(code, no_update=True)

            code.b2b_sheet_location = row
            codes.append(code)

            row_idx += 1

        Discount.objects.bulk_update(codes, {"b2b_sheet_location"})

        return row_idx - self.row_one
