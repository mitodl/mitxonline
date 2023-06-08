"""
Fixtures for hubspot_sync tests
"""
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytz
import reversion
from django.contrib.contenttypes.models import ContentType
from hubspot.crm.objects import SimplePublicObject
from mitol.hubspot_api.factories import HubspotObjectFactory
from reversion.models import Version

from ecommerce import factories
from ecommerce.models import Order, Product
from users.models import User

# pylint: disable=redefined-outer-name

TIMESTAMPS = [
    datetime(2017, 1, 1, tzinfo=pytz.utc),
    datetime(2017, 1, 2, tzinfo=pytz.utc),
    datetime(2017, 1, 3, tzinfo=pytz.utc),
    datetime(2017, 1, 4, tzinfo=pytz.utc),
    datetime(2017, 1, 5, tzinfo=pytz.utc),
    datetime(2017, 1, 6, tzinfo=pytz.utc),
    datetime(2017, 1, 7, tzinfo=pytz.utc),
    datetime(2017, 1, 8, tzinfo=pytz.utc),
]

FAKE_OBJECT_ID = 1234
FAKE_HUBSPOT_ID = "1231213123"


@pytest.fixture
def mocked_celery(mocker):
    """Mock object that patches certain celery functions"""
    exception_class = TabError
    replace_mock = mocker.patch(
        "celery.app.task.Task.replace", autospec=True, side_effect=exception_class
    )
    group_mock = mocker.patch("celery.group", autospec=True)
    chain_mock = mocker.patch("celery.chain", autospec=True)

    yield SimpleNamespace(
        replace=replace_mock,
        group=group_mock,
        chain=chain_mock,
        replace_exception_class=exception_class,
    )


@pytest.fixture
def mock_logger(mocker):
    """Mock the logger"""
    yield mocker.patch("hubspot_sync.tasks.log.error")


@pytest.fixture
def hubspot_order():
    """Return an order for testing with hubspot"""
    order = factories.OrderFactory()
    with reversion.create_revision():
        product = factories.ProductFactory.create(price=Decimal(200.00))

    factories.LineFactory.create(
        order=order,
        product_version=Version.objects.get_for_object(product).first(),
        purchased_object=product.purchasable_object,
    )

    HubspotObjectFactory.create(
        content_object=order.purchaser,
        content_type=ContentType.objects.get_for_model(User),
        object_id=order.purchaser.id,
    )
    HubspotObjectFactory.create(
        content_object=product,
        content_type=ContentType.objects.get_for_model(Product),
        object_id=product.id,
    )

    return order


@pytest.fixture
def hubspot_order_id(hubspot_order):
    """Create a HubspotObject for hubspot_order"""
    return HubspotObjectFactory.create(
        content_object=hubspot_order,
        content_type=ContentType.objects.get_for_model(Order),
        object_id=hubspot_order.id,
    ).hubspot_id


@pytest.fixture
def mock_hubspot_api(mocker):
    """Mock the Hubspot CRM API"""
    mock_api = mocker.patch("mitol.hubspot_api.api.HubspotApi")
    mock_api.return_value.crm.objects.basic_api.create.return_value = (
        SimplePublicObject(id=FAKE_HUBSPOT_ID)
    )
    yield mock_api
