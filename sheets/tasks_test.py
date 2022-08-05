import pytest

from mitol.google_sheets_refunds.api import RefundRequestHandler

from sheets.tasks import process_refund_requests


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_configured",
    [True, False],
)
def test_process_refund_requests(mocker, user, is_configured):
    """
    Test that process_refund_requests calls process_sheet only if it is properly configured
    """
    Mock = mocker.Mock
    MagicMock = mocker.MagicMock
    refund_req_handler = MagicMock(
        spec=RefundRequestHandler, process_sheet=Mock(), is_configured=Mock()
    )
    refund_req_handler_mock = mocker.patch(
        "sheets.tasks.RefundRequestHandler",
        return_value=refund_req_handler,
    )
    refund_req_handler.is_configured.return_value = is_configured

    process_refund_requests.delay()
    refund_req_handler_mock.assert_called()
    refund_req_handler.is_configured.assert_called()
    if is_configured:
        refund_req_handler.process_sheet.assert_called()
    else:
        assert not refund_req_handler.process_sheet.called
