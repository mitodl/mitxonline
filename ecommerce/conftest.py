"""Common fixtures for ecommerce tests"""
import pytest


@pytest.fixture(autouse=True)
def mocked_hubspot_deal_sync(mocker):
    return mocker.patch("hubspot_sync.task_helpers.sync_hubspot_deal")
