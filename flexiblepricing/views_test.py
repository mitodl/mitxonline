import pytest
from django.urls import reverse
from rest_framework import status

from flexiblepricing import models
from flexiblepricing.factories import (
    FlexiblePriceFactory,
    FlexiblePriceTierFactory,
)

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def flexible_price_application():
    return FlexiblePriceFactory.create()


@pytest.mark.skip_nplusone_check
def test_finaid_admin(
    admin_drf_client, user, flexible_price_application, mocker
):
    """
    Test basic operation of the financial assistance admin viewset.
    """
    mocker.patch(
        "flexiblepricing.tasks.notify_flexible_price_status_change_email.delay"
    )
    myapp = flexible_price_application
    myapp.user = user
    myapp.pk = None
    myapp.save()

    allapps = models.FlexiblePrice.objects.all()

    resp = admin_drf_client.get(reverse("fp_admin_flexiblepricing_api-list"))
    json_response = resp.json()
    assert resp.status_code == status.HTTP_200_OK
    assert json_response["count"] == allapps.count()

    new_discount = FlexiblePriceTierFactory(
        courseware_object=flexible_price_application.courseware_object
    ).discount
    financial_assistance_request_data = {
        "status": "approved",
        "justification": "Documents in order",
        "discount": {"id": new_discount.id},
    }
    resp = admin_drf_client.patch(
        reverse(
            "fp_admin_flexiblepricing_api-detail",
            kwargs={"pk": flexible_price_application.id},
        ),
        financial_assistance_request_data,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert (
        models.FlexiblePrice.objects.get(
            id=flexible_price_application.id
        ).tier.discount_id
        == new_discount.id
    )
