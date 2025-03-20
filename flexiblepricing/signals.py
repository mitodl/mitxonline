"""
Signals for mitxonline course certificates
"""

import requests
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.models import FlexiblePrice


@receiver(
    post_save,
    sender=FlexiblePrice,
    dispatch_uid="flexibleprice_post_save",
)
def handle_flexible_price_save(
    sender,  # pylint: disable=unused-argument  # noqa: ARG001
    instance,
    created, # pylint: disable=unused-argument  # noqa: ARG001
    **kwargs,  # pylint: disable=unused-argument  # noqa: ARG001
):
    """
    When a FlexiblePrice is saved.
    """

    if instance.status == FlexiblePriceStatus.APPROVED:
        with transaction.atomic():
            url = "http://host.docker.internal:9080//api/v0/payments/discounts/"

            # Discount data
            discount_data = {
                "discount_code": "WELCOME2024",
                "discount_type": "percent-off",
                "amount": 10.00,  # 10% off
                "activation_date": "2024-03-19",
                "expiration_date": "2024-12-31",
                "max_redemptions": 100,
                "description": "Welcome discount for new users",
                "payment_type": "financial-assistance",
            }

            # Make POST request
            response = requests.post(url, json=discount_data, headers={"Authorization": "Api-Key 2BzQwz7b.Mn96w8OGpLnhVBTRVA5XM6scLSgG5WLg"})
            
            if response.status_code == 201:
                print("Discount created successfully!")
                print(response.json())
            else:
                print(f"Error creating discount: {response.status_code}")
                print(response.json())
