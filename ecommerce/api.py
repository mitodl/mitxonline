"""Ecommerce APIs"""

from django.urls import reverse
from main.settings import ECOMMERCE_DEFAULT_PAYMENT_GATEWAY

from mitol.payment_gateway.api import (
    CartItem as GatewayCartItem,
    Order as GatewayOrder,
    PaymentGateway,
)
from mitol.common.utils.datetime import now_in_utc
from ipware import get_client_ip

from ecommerce.models import Basket, PendingOrder, UserDiscount, BasketDiscount


def generate_checkout_payload(request):
    basket = Basket.objects.filter(user=request.user).get()
    order = PendingOrder.create_from_basket(basket)

    ip = get_client_ip(request)[0]

    gateway_order = GatewayOrder(
        username=request.user.username,
        ip_address=ip,
        reference=order.reference_number,
        items=[],
    )

    for line_item in order.lines.all():
        field_dict = line_item.product_version.field_dict
        gateway_order.items.append(
            GatewayCartItem(
                code=field_dict["content_type_id"],
                name=field_dict["description"],
                quantity=1,
                sku=f"{field_dict['content_type_id']}-{field_dict['object_id']}",
                unitprice=line_item.discounted_price,
                taxable=0,
            )
        )

    callback_uri = request.build_absolute_uri(reverse("checkout-result-callback"))

    payload = PaymentGateway.start_payment(
        ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,
        gateway_order,
        callback_uri,
        callback_uri,
    )

    return payload


def apply_user_discounts(user):
    """
    Applies user discounts to the current cart. (If there are more than one for some
    reason, this will just do the first one. More logic needs to be added here
    if/when discounts apply to specific things.)

    Args:
        - user (User): The currently authenticated user.
    """
    basket = Basket.objects.filter(user=user).get()

    if BasketDiscount.objects.filter(redeemed_basket=basket).count() > 0:
        return True

    user_discounts = UserDiscount.objects.filter(user=user).all()

    for discount in user_discounts:
        bd = BasketDiscount(
            redeemed_basket=basket,
            redemption_date=now_in_utc(),
            redeemed_by=user,
            redeemed_discount=discount.discount,
        )
        bd.save()

    return True
