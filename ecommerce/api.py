"""Ecommerce APIs"""

import json
import logging

from functools import total_ordering
from django.urls import reverse
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from main.settings import ECOMMERCE_DEFAULT_PAYMENT_GATEWAY
from main.utils import redirect_with_user_message
from ecommerce.constants import TRANSACTION_TYPE_REFUND, REFUND_SUCCESS_STATES
from ecommerce.tasks import perform_unenrollment_from_order
from courses.api import deactivate_run_enrollment
from courses.constants import ENROLL_CHANGE_STATUS_REFUNDED
from main.constants import (
    USER_MSG_TYPE_PAYMENT_ACCEPTED,
    USER_MSG_TYPE_PAYMENT_ACCEPTED_NOVALUE,
    USER_MSG_TYPE_ENROLL_BLOCKED,
    USER_MSG_TYPE_ENROLL_DUPLICATED,
    USER_MSG_TYPE_COURSE_NON_UPGRADABLE,
)

from mitol.payment_gateway.api import (
    CartItem as GatewayCartItem,
    Order as GatewayOrder,
    PaymentGateway,
    Refund as GatewayRefund,
)
from mitol.payment_gateway.exceptions import RefundDuplicateException

from mitol.common.utils.datetime import now_in_utc
from ipware import get_client_ip

from ecommerce.models import (
    Basket,
    BasketItem,
    PendingOrder,
    UserDiscount,
    BasketDiscount,
    FulfilledOrder,
    Transaction,
    Order,
    Discount,
    DiscountProduct,
)
from flexiblepricing.api import determine_courseware_flexible_price_discount

log = logging.getLogger(__name__)


def generate_checkout_payload(request):
    basket = Basket.objects.filter(user=request.user).get()

    if basket.has_user_blocked_products(request.user):
        return {
            "country_blocked": True,
            "response": redirect_with_user_message(
                reverse("user-dashboard"),
                {"type": USER_MSG_TYPE_ENROLL_BLOCKED},
            ),
        }

    if basket.has_user_purchased_same_courserun(request.user):
        return {
            "purchased_same_courserun": True,
            "response": redirect_with_user_message(
                reverse("cart"),
                {"type": USER_MSG_TYPE_ENROLL_DUPLICATED},
            ),
        }

    if basket.has_user_purchased_non_upgradable_courserun():
        return {
            "purchased_non_upgradeable_courserun": True,
            "response": redirect_with_user_message(
                reverse("cart"),
                {"type": USER_MSG_TYPE_COURSE_NON_UPGRADABLE},
            ),
        }

    basket = establish_basket(request)

    order = PendingOrder.create_from_basket(basket)
    total_price = 0

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
        total_price += line_item.discounted_price

    if total_price == 0:
        return {
            "no_checkout": True,
            "response": fulfill_completed_order(
                order,
                {"amount": 0, "data": {"reason": "No payment required"}},
                basket,
                USER_MSG_TYPE_PAYMENT_ACCEPTED_NOVALUE,
            ),
        }

    callback_uri = request.build_absolute_uri(reverse("checkout-result-callback"))

    payload = PaymentGateway.start_payment(
        ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,
        gateway_order,
        callback_uri,
        callback_uri,
        merchant_fields=[basket.id],
    )

    return payload


def check_discount_for_products(discount, basket):
    """
    Checks the validity of the discount against what's in the basket.

    If the discount either has no products associated with it, or the products
    in the basket are applicable to the discount, this returns True.
    Otherwise, returns False.

    Args:
        - basket (Basket): the current basket
        - discount (Discount|string: the discount to apply (if a string, loads the discount code specified)
    Returns:
        boolean
    """
    if not isinstance(discount, Discount):
        discount = Discount.objects.filter(discount_code=discount).first()

    basket_products = basket.get_products()

    return (
        not discount.products.exists()
        or DiscountProduct.objects.filter(product__in=basket_products)
        .filter(discount=discount)
        .exists()
    )


def apply_user_discounts(request):
    """
    Applies user discounts to the current cart. (If there are more than one for some
    reason, this will just do the first one. More logic needs to be added here
    if/when discounts apply to specific things.)

    Args:
        - user (User): The currently authenticated user.

    Returns:
        None
    """
    basket = establish_basket(request)
    user = request.user
    discount = None

    if BasketDiscount.objects.filter(redeemed_basket=basket).count() > 0:
        return

    product = BasketItem.objects.get(basket=basket).product
    flexible_price_discount = determine_courseware_flexible_price_discount(
        product, user
    )
    if flexible_price_discount:
        discount = flexible_price_discount
    else:
        user_discount = UserDiscount.objects.filter(user=user).first()
        if user_discount:
            discount = user_discount.discount

    if discount:
        # check for product specificity in the discount
        if not check_discount_for_products(discount, basket):
            return

        bd = BasketDiscount(
            redeemed_basket=basket,
            redemption_date=now_in_utc(),
            redeemed_by=user,
            redeemed_discount=discount,
        )
        bd.save()

    return


def fulfill_completed_order(
    order, payment_data, basket, message_type=USER_MSG_TYPE_PAYMENT_ACCEPTED
):
    order.fulfill(payment_data)
    order.save()

    if not order.is_review and (basket and basket.compare_to_order(order)):
        basket.delete()

    return redirect_with_user_message(
        reverse("user-dashboard"),
        {
            "type": message_type,
            "run": order.lines.first().purchased_object.course.title,
        },
    )


def establish_basket(request):
    """
    Gets or creates the user's basket. (This may get some more logic later.)
    """
    user = request.user
    (basket, is_new) = Basket.objects.filter(user=user).get_or_create()

    if is_new:
        basket.save()

    return basket


def refund_order(*, order_id: int, **kwargs):
    """
    A function that performs refund for a given order id

    Args:
       order_id (int): Id of the order which is being refunded
       kwargs (dict): Dictionary of the other attributes that are passed e.g. refund amount, refund reason, unenroll
       If no refund_amount is provided it will use refund amount from Transaction obj
       unenroll will never be performed if the refund fails

    Returns:
        bool : A boolean identifying if an order refund was successful
    """
    refund_amount = kwargs.get("refund_amount")
    refund_reason = kwargs.get("refund_reason", "")
    unenroll = kwargs.get("unenroll", False)

    with transaction.atomic():

        order = FulfilledOrder.objects.select_for_update().get(id=order_id)

        if order.state != Order.STATE.FULFILLED:
            log.debug(f"Order with order_id {order_id} is not in fulfilled state.")
            return False

        order_recent_transaction = Transaction.objects.filter(order=order_id).first()

        if not order_recent_transaction:
            log.error(
                f"There is no associated transaction against order_id {order_id}."
            )
            return False

        transaction_dict = order_recent_transaction.data

        # The refund amount can be different then the payment amount, so we override
        # that before PaymentGateway processing.
        # e.g. While refunding order from Django Admin we can select custom amount.
        if refund_amount:
            transaction_dict["req_amount"] = refund_amount

        refund_transaction = order.refund(
            api_response_data={},
            amount=transaction_dict["req_amount"],
            reason=refund_reason,
        )

        refund_gateway_request = PaymentGateway.create_refund_request(
            ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, transaction_dict
        )

        try:
            response = PaymentGateway.start_refund(
                ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,
                refund_gateway_request,
            )
            if response.state in REFUND_SUCCESS_STATES:
                # Update the above created refund transaction with PaymentGateway's refund response
                refund_transaction.data = response.response_data
                refund_transaction.save()

            else:
                log.error(
                    f"There was an error with the Refund API request {response.message}"
                )
                # PaymentGateway didn't raise an exception and instead gave a Response but the response status was not
                # success so we manually rollback the transaction in this case.
                transaction.set_rollback()
                # Just return here if the refund failed, no matter if unenroll was requested or not
                return False

        except RefundDuplicateException:
            # Duplicate refund error during the API call will be treated as success, we just log it
            log.info(f"Duplicate refund request for order_id {order_id}")

    # If unenroll requested, perform unenrollment after successful refund
    if unenroll:
        perform_unenrollment_from_order.delay(order_id)

    return True


def unenroll_learner_from_order(order_id):
    """
    A function that un-enrolls a learner from all the courses associated with specific order
    """
    order = Order.objects.get(pk=order_id)

    for run in order.purchased_runs:
        for enrollment in run.enrollments.filter(user=order.purchaser).all():
            try:
                if (
                    deactivate_run_enrollment(enrollment, ENROLL_CHANGE_STATUS_REFUNDED)
                    is None
                ):
                    deactivate_run_enrollment(
                        enrollment,
                        ENROLL_CHANGE_STATUS_REFUNDED,
                        keep_failed_enrollments=True,
                    )
            except ObjectDoesNotExist:
                pass
