"""Tests for multiple cart items functionality"""

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from ecommerce.factories import BasketFactory, BasketItemFactory, ProductFactory


@pytest.mark.django_db
class TestMultipleCartItems:
    """Test class for multiple cart items functionality"""

    @override_settings(ENABLE_MULTIPLE_CART_ITEMS=False)
    def test_add_to_cart_single_item_mode_default(self, user_drf_client, user):
        """Test that with feature flag disabled, adding items replaces existing items"""
        # Create a product and basket with existing item
        existing_product = ProductFactory.create()
        new_product = ProductFactory.create()

        basket = BasketFactory.create(user=user)
        BasketItemFactory.create(basket=basket, product=existing_product)

        assert basket.basket_items.count() == 1

        # Add new product to cart
        response = user_drf_client.post(
            reverse("checkout_api-add_to_cart"),
            data={"product_id": new_product.id},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Product added to cart"

        # Verify that only the new product is in the basket
        basket.refresh_from_db()
        assert basket.basket_items.count() == 1
        assert basket.basket_items.first().product == new_product

    @override_settings(ENABLE_MULTIPLE_CART_ITEMS=True)
    def test_add_to_cart_multiple_items_mode_new_product(self, user_drf_client, user):
        """Test that with feature flag enabled, adding new items keeps existing items"""
        # Create products and basket with existing item
        existing_product = ProductFactory.create()
        new_product = ProductFactory.create()

        basket = BasketFactory.create(user=user)
        BasketItemFactory.create(basket=basket, product=existing_product)

        assert basket.basket_items.count() == 1

        # Add new product to cart
        response = user_drf_client.post(
            reverse("checkout_api-add_to_cart"),
            data={"product_id": new_product.id},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Product added to cart"

        # Verify that both products are in the basket
        basket.refresh_from_db()
        assert basket.basket_items.count() == 2
        products_in_basket = {item.product for item in basket.basket_items.all()}
        assert products_in_basket == {existing_product, new_product}

    @override_settings(ENABLE_MULTIPLE_CART_ITEMS=True)
    def test_add_to_cart_nonexistent_product(self, user_drf_client):
        """Test that adding a non-existent product returns 404"""
        # Add non-existent product to cart
        response = user_drf_client.post(
            reverse("checkout_api-add_to_cart"),
            data={"product_id": 99999},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["message"] == "Product not found"

    @override_settings(ENABLE_MULTIPLE_CART_ITEMS=True)
    def test_cart_with_multiple_items_pricing(self, user_drf_client, user):
        """Test that cart pricing works correctly with multiple items"""
        # Create products with different prices
        product1 = ProductFactory.create(price=50.00)
        product2 = ProductFactory.create(price=30.00)

        basket = BasketFactory.create(user=user)
        BasketItemFactory.create(basket=basket, product=product1, quantity=2)
        BasketItemFactory.create(basket=basket, product=product2, quantity=1)

        # Get cart info
        response = user_drf_client.get(reverse("checkout_api-cart"))

        assert response.status_code == status.HTTP_200_OK
        cart_data = response.data

        # Verify total price calculation (2 * $50 + 1 * $30 = $130)
        assert float(cart_data["total_price"]) == 130.00
        assert len(cart_data["basket_items"]) == 2

    def test_basket_items_count_endpoint(self, user_drf_client, user):
        """Test that basket items count endpoint works with multiple items"""
        # Create products and add to basket
        product1 = ProductFactory.create()
        product2 = ProductFactory.create()

        basket = BasketFactory.create(user=user)
        BasketItemFactory.create(basket=basket, product=product1, quantity=2)
        BasketItemFactory.create(basket=basket, product=product2, quantity=1)

        # Get basket items count
        response = user_drf_client.get(reverse("checkout_api-basket_items_count"))

        assert response.status_code == status.HTTP_200_OK
        # Should return count of distinct items, not total quantity
        assert response.data == 2

    @override_settings(ENABLE_MULTIPLE_CART_ITEMS=False)
    def test_existing_basket_item_viewset_still_works(self, user_drf_client, user):
        """Test that the existing BasketItemViewSet still works regardless of feature flag"""
        product1 = ProductFactory.create()
        product2 = ProductFactory.create()

        basket = BasketFactory.create(user=user)
        BasketItemFactory.create(basket=basket, product=product1)

        # Add item using the existing ViewSet endpoint
        response = user_drf_client.post(
            f"/api/baskets/{basket.id}/items/",
            data={"product": product2.id},
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify both items are in basket
        assert basket.basket_items.count() == 2
