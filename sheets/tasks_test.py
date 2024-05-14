import pytest
from mitol.google_sheets_deferrals.api import DeferralRequestHandler
from mitol.google_sheets_refunds.api import RefundRequestHandler

from sheets.tasks import process_google_sheets_requests


@pytest.mark.django_db
@pytest.mark.parametrize(
    "refunds_is_configured, deferrals_is_configured",  # noqa: PT006
    [(True, True), (False, False)],
)
def test_process_google_sheets_requests(
    mocker, user, refunds_is_configured, deferrals_is_configured
):
    """
    Test that process_google_sheets_requests calls process_sheet only if it is properly configured
    """
    Mock = mocker.Mock
    MagicMock = mocker.MagicMock
    refund_req_handler = MagicMock(
        spec=RefundRequestHandler, process_sheet=Mock(), is_configured=Mock()
    )
    deferral_req_handler = MagicMock(
        spec=DeferralRequestHandler, process_sheet=Mock(), is_configured=Mock()
    )
    refund_req_handler_mock = mocker.patch(
        "sheets.tasks.RefundRequestHandler",
        return_value=refund_req_handler,
    )
    deferral_req_handler_mock = mocker.patch(
        "sheets.tasks.DeferralRequestHandler",
        return_value=deferral_req_handler,
    )
    refund_req_handler.is_configured.return_value = refunds_is_configured
    deferral_req_handler.is_configured.return_value = deferrals_is_configured

    process_google_sheets_requests.delay()
    refund_req_handler_mock.assert_called()
    refund_req_handler.is_configured.assert_called()
    deferral_req_handler_mock.assert_called()
    deferral_req_handler.is_configured.assert_called()
    if refunds_is_configured:
        refund_req_handler.process_sheet.assert_called()
    else:
        assert not refund_req_handler.process_sheet.called

    if deferrals_is_configured:
        deferral_req_handler.process_sheet.assert_called()
    else:
        assert not deferral_req_handler.process_sheet.called
