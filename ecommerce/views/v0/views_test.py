"""View tests for the v0 API."""

import pytest
from django.urls import reverse

from ecommerce.factories import (
    BasketFactory,
    DiscountFactory,
    OrderFactory,
    ProductFactory,
)
from ecommerce.models import Basket, DiscountRedemption

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("existing_basket", [True, False])
@pytest.mark.parametrize("add_discount", [True, False])
@pytest.mark.parametrize("bad_product", [True, False])
def test_create_basket_with_products(
    user, user_client, existing_basket, add_discount, bad_product
):
    """Test creating a basket with products."""

    products = ProductFactory.create_batch(size=2)

    basket = BasketFactory(user=user) if existing_basket else None

    url = reverse("v0:create_with_products")
    payload = {
        "product_ids": [
            {"product_id": -3 if bad_product else product.id, "quantity": 1}
            for product in products
        ],
    }

    if add_discount:
        discount = DiscountFactory(discount_type="fixed-price", amount=100)
        payload["discount_code"] = discount.discount_code

    response = user_client.post(
        url,
        data=payload,
        content_type="application/json",
    )

    if bad_product:
        assert response.status_code == 404
        return

    assert response.status_code == 200

    basket_id = response.data["id"]
    assert Basket.objects.get(id=basket_id).basket_items.count() == 2

    if existing_basket:
        assert basket
        assert basket_id == basket.id

    if add_discount:
        assert (
            Basket.objects.get(id=basket_id)
            .discounts.filter(redeemed_discount=discount)
            .exists()
        )


@pytest.mark.parametrize(
    ("existing_basket", "add_discount", "bad_discount"),
    [
        (True, False, False),
        (False, True, False),
        (False, False, False),
        (False, True, True),
    ],
)
def test_create_basket_with_product(
    user, user_client, existing_basket, add_discount, bad_discount
):
    """Test creating a basket with a single product, and/or a discount."""

    product = ProductFactory.create()

    basket = BasketFactory(user=user) if existing_basket else None

    url = reverse(
        "v0:create_from_product",
        kwargs={"product_id": product.id},
    )

    if add_discount:
        if bad_discount:
            discount = DiscountFactory(
                discount_type="fixed-price", amount=100, max_redemptions=1
            )
            order = OrderFactory.create()
            DiscountRedemption.objects.create(
                redeemed_by=order.purchaser,
                redemption_date=order.created_on,
                redeemed_discount=discount,
                redeemed_order=order,
            )
        else:
            discount = DiscountFactory(discount_type="fixed-price", amount=100)

        url = reverse(
            "v0:create_from_product_with_discount",
            kwargs={
                "product_id": product.id,
                "discount_code": discount.discount_code,
            },
        )

    response = user_client.post(url)

    # This returns a 201 if we created the _basket line item_.
    assert response.status_code >= 200
    assert response.status_code < 300

    basket_id = response.data["id"]
    assert Basket.objects.get(id=basket_id).basket_items.count() == 1

    if existing_basket:
        assert basket
        assert basket_id == basket.id

    if add_discount:
        if bad_discount:
            assert (
                not Basket.objects.get(id=basket_id)
                .discounts.filter(redeemed_discount=discount)
                .exists()
            )
        else:
            assert (
                Basket.objects.get(id=basket_id)
                .discounts.filter(redeemed_discount=discount)
                .exists()
            )
