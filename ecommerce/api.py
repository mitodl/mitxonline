"""Ecommerce APIs"""

from django.urls import reverse
from main.settings import ECOMMERCE_DEFAULT_PAYMENT_GATEWAY

from mitol.payment_gateway.api import (
    CartItem as GatewayCartItem,
    Order as GatewayOrder,
    PaymentGateway,
)
from ipware import get_client_ip

from ecommerce.models import (
    Basket,
    PendingOrder,
)


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
