"""Ecommerce APIs"""

import logging

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from ipware import get_client_ip
from mitol.common.utils.datetime import now_in_utc
from mitol.payment_gateway.api import CartItem as GatewayCartItem
from mitol.payment_gateway.api import Order as GatewayOrder
from mitol.payment_gateway.api import PaymentGateway, ProcessorResponse
from mitol.payment_gateway.exceptions import RefundDuplicateException

from courses.api import deactivate_run_enrollment
from courses.constants import ENROLL_CHANGE_STATUS_REFUNDED
from ecommerce.constants import REFUND_SUCCESS_STATES, ZERO_PAYMENT_DATA, PAYMENT_TYPE_FINANCIAL_ASSISTANCE
from ecommerce.models import (
    Basket,
    BasketDiscount,
    BasketItem,
    Discount,
    FulfilledOrder,
    Order,
    PendingOrder,
    UserDiscount,
)
from ecommerce.tasks import perform_unenrollment_from_order
from flexiblepricing.api import determine_courseware_flexible_price_discount
from hubspot_sync.task_helpers import sync_hubspot_deal
from main.constants import (
    USER_MSG_TYPE_COURSE_NON_UPGRADABLE,
    USER_MSG_TYPE_DISCOUNT_INVALID,
    USER_MSG_TYPE_ENROLL_BLOCKED,
    USER_MSG_TYPE_ENROLL_DUPLICATED,
    USER_MSG_TYPE_PAYMENT_ACCEPTED_NOVALUE,
)
from main.settings import ECOMMERCE_DEFAULT_PAYMENT_GATEWAY
from main.utils import redirect_with_user_message

log = logging.getLogger(__name__)


def generate_checkout_payload(request):
    basket = establish_basket(request)

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

    if not check_basket_discounts_for_validity(request):
        # We only allow one discount per basket so clear all of them here.
        basket.discounts.all().delete()
        apply_user_discounts(request)
        return {
            "invalid_discounts": True,
            "response": redirect_with_user_message(
                reverse("cart"),
                {"type": USER_MSG_TYPE_DISCOUNT_INVALID},
            ),
        }

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
        with transaction.atomic():
            fulfill_completed_order(
                order, payment_data=ZERO_PAYMENT_DATA, basket=basket
            )
            return {
                "no_checkout": True,
                "response": redirect_with_user_message(
                    reverse("user-dashboard"),
                    {
                        "type": USER_MSG_TYPE_PAYMENT_ACCEPTED_NOVALUE,
                        "run": order.lines.first().purchased_object.course.title,
                    },
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

    return discount.check_validity_with_products(basket_products)


def check_basket_discounts_for_validity(request):
    basket = establish_basket(request)

    for basket_discount in basket.discounts.all():
        if not basket_discount.redeemed_discount.check_validity(
            basket.user
        ) or not check_discount_for_products(basket_discount.redeemed_discount, basket):
            return False

    return True


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

    BasketDiscount.objects.filter(
        redeemed_basket=basket, redeemed_discount__payment_type=PAYMENT_TYPE_FINANCIAL_ASSISTANCE
    ).delete()
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
        if not check_discount_for_products(
            discount, basket
        ) or not discount.check_validity(user):
            return

        bd = BasketDiscount(
            redeemed_basket=basket,
            redemption_date=now_in_utc(),
            redeemed_by=user,
            redeemed_discount=discount,
        )
        bd.save()

    return


def fulfill_completed_order(order, payment_data, basket=None, already_enrolled=False):
    order.fulfill(payment_data, already_enrolled=already_enrolled)
    order.save()

    if basket and basket.compare_to_order(order):
        basket.delete()


def get_order_from_cybersource_payment_response(request):
    payment_data = request.POST
    converted_order = PaymentGateway.get_gateway_class(
        ECOMMERCE_DEFAULT_PAYMENT_GATEWAY
    ).convert_to_order(payment_data)
    order_id = Order.decode_reference_number(converted_order.reference)

    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except ObjectDoesNotExist:
        order = None
    return order


def process_cybersource_payment_response(request, order):
    """
    Updates the order and basket based on the payment request from Cybersource.
    Returns the order state after applying update operations corresponding to the request.

    Args:
        - request (HttpRequest): The payment request received from Cybersource.
        - order (Order): The order corresponding to the request payload.
    Returns:
        Order.state
    """

    if not PaymentGateway.validate_processor_response(
        ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
    ):
        raise PermissionDenied(
            "Could not validate response from the payment processor."
        )

    processor_response = PaymentGateway.get_formatted_response(
        ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
    )

    # Log message if reason_code is anything other than 100 (successful transaction)
    # only log 1xx as errors for now
    reason_code = processor_response.response_code
    transaction_id = processor_response.transaction_id
    if reason_code and reason_code.isdigit():
        reason_code = int(reason_code)
        message = "Transaction was not successful. Transaction ID:%s  Reason Code:%d  Message:%s"
        if 100 < reason_code < 200:
            log.error(message, transaction_id, reason_code, processor_response.message)
        elif reason_code >= 200:
            log.debug(message, transaction_id, reason_code, processor_response.message)

    return_message = ""

    if processor_response.state == ProcessorResponse.STATE_DECLINED:
        # Transaction declined for some reason
        # This probably means the order needed to go through the process
        # again so maybe tell the user to do a thing.
        log.debug("Transaction declined: {msg}".format(msg=processor_response.message))
        order.decline()
        order.save()
        return_message = order.state
    elif processor_response.state == ProcessorResponse.STATE_ERROR:
        # Error - something went wrong with the request
        log.debug(
            "Error happened submitting the transaction: {msg}".format(
                msg=processor_response.message
            )
        )
        order.error()
        order.save()
        return_message = order.state
    elif processor_response.state in [
        ProcessorResponse.STATE_CANCELLED,
        ProcessorResponse.STATE_REVIEW,
    ]:
        # Transaction cancelled or reviewed
        # Transaction could be cancelled for reasons that don't necessarily
        # mean that the entire order is invalid, so we'll do nothing with
        # the order here (other than set it to Cancelled).
        # Transaction could be
        log.debug(
            "Transaction cancelled/reviewed: {msg}".format(
                msg=processor_response.message
            )
        )
        order.cancel()
        order.save()
        return_message = order.state

    elif (
        processor_response.state == ProcessorResponse.STATE_ACCEPTED
        or reason_code == 100
    ):
        # It actually worked here
        basket = Basket.objects.filter(user=order.purchaser).first()
        try:
            log.debug(
                "Transaction accepted!: {msg}".format(msg=processor_response.message)
            )
            fulfill_completed_order(order, request.POST, basket)
        except ValidationError:
            log.debug(
                "Missing transaction id from transaction response: {msg}".format(
                    msg=processor_response.message
                )
            )
            raise

        return_message = order.state
    else:
        log.error(
            f"Unknown state {processor_response.state} found: transaction ID {transaction_id}, reason code {reason_code}, response message {processor_response.message}"
        )
        order.cancel()
        order.save()
        return_message = order.state

    return return_message


def establish_basket(request):
    """
    Gets or creates the user's basket. (This may get some more logic later.)
    """
    user = request.user
    (basket, is_new) = Basket.objects.filter(user=user).get_or_create()

    if is_new:
        basket.save()

    return basket


def refund_order(*, order_id: int = None, reference_number: str = None, **kwargs):
    """
    A function that performs refund for a given order id

    Args:
       order_id (int): Id or reference_number of the order which is being refunded
       reference_number (str): Reference number of the order
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
        if reference_number is not None:
            order = FulfilledOrder.objects.select_for_update().get(
                reference_number=reference_number
            )
        elif order_id is not None:
            order = FulfilledOrder.objects.select_for_update().get(pk=order_id)
        else:
            log.error(
                "Either order_id or reference_number is required to fetch the Order."
            )
            return False
        if order.state != Order.STATE.FULFILLED:
            log.debug("Order with order_id %s is not in fulfilled state.", order.id)
            return False

        order_recent_transaction = order.transactions.first()

        if not order_recent_transaction:
            log.error(
                "There is no associated transaction against order_id %s", order.id
            )
            return False

        transaction_dict = order_recent_transaction.data

        # The refund amount can be different then the payment amount, so we override
        # that before PaymentGateway processing.
        # e.g. While refunding order from Django Admin we can select custom amount.
        if refund_amount:
            transaction_dict["req_amount"] = refund_amount

        refund_gateway_request = PaymentGateway.create_refund_request(
            ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, transaction_dict
        )

        try:
            response = PaymentGateway.start_refund(
                ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,
                refund_gateway_request,
            )

            if response.state in REFUND_SUCCESS_STATES:
                # Record refund transaction with PaymentGateway's refund response
                order.refund(
                    api_response_data=response.response_data,
                    amount=transaction_dict["req_amount"],
                    reason=refund_reason,
                )

            else:
                log.error(
                    "There was an error with the Refund API request %s",
                    response.message,
                )
                # PaymentGateway didn't raise an exception and instead gave a Response but the response status was not
                # success so we manually rollback the transaction in this case.
                transaction.set_rollback()
                # Just return here if the refund failed, no matter if unenroll was requested or not
                return False

        except RefundDuplicateException:
            # Duplicate refund error during the API call will be treated as success, we just log it
            log.info("Duplicate refund request for order_id %s", order.id)

    # If unenroll requested, perform unenrollment after successful refund
    if unenroll:
        perform_unenrollment_from_order.delay(order.id)

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
