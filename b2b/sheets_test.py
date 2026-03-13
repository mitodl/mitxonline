# ruff: noqa: SLF001
"""Tests for the Google Shees enrollment code integration."""

import logging
from unittest.mock import ANY, MagicMock

import faker
import pytest
from mitol.google_sheets.constants import GOOGLE_SHEET_FIRST_ROW

from b2b import factories
from b2b.api import ensure_contract_run_products, ensure_enrollment_codes_exist
from b2b.constants import CONTRACT_MEMBERSHIP_CODE, CONTRACT_MEMBERSHIP_MANAGED
from b2b.models import DiscountContractAttachmentRedemption
from b2b.sheets import ContractEnrollmentCodesSheetHandler
from courses.factories import CourseRunFactory
from users.factories import UserFactory

FAKE = faker.Faker()
pytestmark = [
    pytest.mark.django_db,
]


@pytest.fixture(autouse=True)
def mocked_pygsheets(mocker, settings):
    """Mock the pygsheets client."""

    settings.MITOL_GOOGLE_SHEETS_DRIVE_SHARED_ID = False

    class FakePygsheetsClient:
        """A faked pygsheets client with some faked methods."""

        open_by_url = MagicMock()

    mocker.patch("mitol.google_sheets.api.get_credentials")

    return mocker.patch(
        "pygsheets.authorize",
        side_effect=lambda *args, **kwargs: FakePygsheetsClient(),  # noqa: ARG005
    )


@pytest.fixture
def contract_with_sheet():
    """Return a ContractPage with the fields set up right for the integration."""

    return factories.ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        integration_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=FAKE.random_int(10, 20),
        google_sheet_target=FAKE.url(),
        google_sheet_target_tab="Sheet1",
    )


@pytest.fixture
def contract_with_sheet_courseruns(contract_with_sheet, mocker):
    """Expand on contract_with_sheet and add course runs/enrollment codes."""

    runs = CourseRunFactory.create_batch(3, b2b_contract=contract_with_sheet)

    mocker.patch("b2b.tasks.queue_contract_sheet_update_post_save.delay")
    ensure_contract_run_products(contract_with_sheet)
    ensure_enrollment_codes_exist(contract_with_sheet)

    return (
        contract_with_sheet,
        runs,
    )


@pytest.mark.parametrize(
    "valid_sheet",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "valid_contract",
    [
        True,
        False,
    ],
)
def test_handler_init(mocked_pygsheets, valid_sheet, valid_contract):
    """Test that the class initializes properly."""

    test_contract = factories.ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE
        if valid_contract
        else CONTRACT_MEMBERSHIP_MANAGED,
        integration_type=CONTRACT_MEMBERSHIP_CODE
        if valid_contract
        else CONTRACT_MEMBERSHIP_MANAGED,
    )

    if valid_sheet:
        test_contract.google_sheet_target = FAKE.url()
        test_contract.save()

    if not valid_sheet or not valid_contract:
        with pytest.raises(ValueError, match=r"can't continue") as exc:
            ContractEnrollmentCodesSheetHandler(test_contract)

        if not valid_sheet:
            assert "no linked Google Sheet" in str(exc)
            return

        if not valid_contract:
            assert "no enrollment codes" in str(exc)

        return

    handler = ContractEnrollmentCodesSheetHandler(test_contract)

    assert handler
    mocked_pygsheets.assert_called()
    # because I will forget this - the mocked_pygsheets returns a custom class
    # with mocked pygsheets Client methods in it.
    handler.pygsheets_client.open_by_url.assert_called_with(
        test_contract.google_sheet_target
    )


def test_row_helpers(contract_with_sheet):
    """Make sure the row helper methods work."""

    handler = ContractEnrollmentCodesSheetHandler(contract_with_sheet)

    assert handler.row_zero == GOOGLE_SHEET_FIRST_ROW
    assert handler.row_one == GOOGLE_SHEET_FIRST_ROW + 1


@pytest.mark.parametrize(
    "row_zero_length",
    [
        0,
        3,
    ],
)
def test_ensure_header(caplog, contract_with_sheet, row_zero_length):
    """Test that the header gets written as expected."""

    handler = ContractEnrollmentCodesSheetHandler(contract_with_sheet)

    row_zero = [] if row_zero_length == 0 else FAKE.random_letters(row_zero_length)

    handler._write_header = MagicMock()
    handler.worksheet.get_row = MagicMock(return_value=row_zero)

    if row_zero_length > 0:
        with caplog.at_level(logging.WARNING):
            handler.ensure_header()

        assert "overwrite" in caplog.text
    else:
        handler.ensure_header()
        handler._write_header.assert_called()


def test_sorted_codes(contract_with_sheet_courseruns):
    """Test that the handler's code retrieval works as expected."""

    contract, _ = contract_with_sheet_courseruns
    users = UserFactory.create_batch(2)

    assert contract.get_discounts().count() == 3 * contract.max_learners

    # Grab a code from the top and bottom of the list, so we can make sure that
    # _all_ redeemed codes make it into the result set.

    first_code = contract.get_discounts().first()
    last_code = contract.get_discounts().last()

    DiscountContractAttachmentRedemption.objects.create(
        contract=contract,
        user=users[0],
        discount=first_code,
    )
    DiscountContractAttachmentRedemption.objects.create(
        contract=contract,
        user=users[0],
        discount=last_code,
    )

    handler = ContractEnrollmentCodesSheetHandler(contract)
    sorted_codes = handler._get_sorted_codes()

    assert sorted_codes.count() == contract.max_learners
    assert first_code.id in [code.id for code in sorted_codes]
    assert last_code.id in [code.id for code in sorted_codes]


def test_formatted_codes(contract_with_sheet_courseruns):
    """Test that the proto-serializer for the sheet works."""

    contract, _ = contract_with_sheet_courseruns
    handler = ContractEnrollmentCodesSheetHandler(contract)
    sorted_codes = handler._get_sorted_codes()

    formatted_code = handler._get_discount_cells(sorted_codes[0])

    assert formatted_code == [
        sorted_codes[0].discount_code,
        sorted_codes[0].redemption_type,
        sorted_codes[0].contract_redemptions.count(),
        "",
        "",
        "",
    ]


def test_write_codes(mocker, contract_with_sheet_courseruns):
    """Test that destructively writing the codes works as expected."""

    contract_with_sheet, _ = contract_with_sheet_courseruns
    handler = ContractEnrollmentCodesSheetHandler(contract_with_sheet)

    handler._write_header = MagicMock()
    handler.worksheet.get_row = MagicMock(return_value=[])
    handler.worksheet.update_row = MagicMock()

    handler.write_codes()

    test_cells = handler._get_discount_cells(handler._get_sorted_codes()[4])
    handler.worksheet.update_row.assert_any_call(ANY, test_cells)
