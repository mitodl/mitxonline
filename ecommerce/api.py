"""Ecommerce APIs"""

import logging
import uuid
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from ipware import get_client_ip
from mitol.common.utils.datetime import now_in_utc
from mitol.payment_gateway.api import CartItem as GatewayCartItem
from mitol.payment_gateway.api import Order as GatewayOrder
from mitol.payment_gateway.api import PaymentGateway, ProcessorResponse
from mitol.payment_gateway.exceptions import RefundDuplicateException

from courses.api import create_run_enrollments, deactivate_run_enrollment
from courses.constants import ENROLL_CHANGE_STATUS_REFUNDED
from ecommerce.constants import (
    ALL_DISCOUNT_TYPES,
    ALL_PAYMENT_TYPES,
    DISCOUNT_TYPE_PERCENT_OFF,
    PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
    REFUND_SUCCESS_STATES,
    ZERO_PAYMENT_DATA,
)
from ecommerce.models import (
    Basket,
    BasketDiscount,
    BasketItem,
    Discount,
    DiscountRedemption,
    FulfilledOrder,
    Order,
    PendingOrder,
    UserDiscount,
)
from ecommerce.tasks import perform_downgrade_from_order
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
from main.utils import parse_supplied_date, redirect_with_user_message
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE

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
        redeemed_basket=basket,
        redeemed_discount__payment_type=PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
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
            transaction.rollback()
            raise Exception(f"Payment gateway returned an error: {response.message}")

    # If unenroll requested, perform unenrollment after successful refund
    if unenroll:
        perform_downgrade_from_order.delay(order.id)

    return True


def downgrade_learner_from_order(order_id):
    """
    Pulls the learner's enrollments from a specified order and downgrades them
    to audit.
    """

    order = Order.objects.get(pk=order_id)

    # Forcing the enrollment here - if the refund comes after the end date
    # for the course for whatever reason, we still want to revert the mode.
    create_run_enrollments(
        user=order.purchaser,
        runs=order.purchased_runs,
        keep_failed_enrollments=True,
        mode=EDX_ENROLLMENT_AUDIT_MODE,
        force_enrollment=True,
    )


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


def check_and_process_pending_orders_for_resolution(refnos=None):
    """
    Checks pending orders for resolution. By default, this will pull all the
    pending orders that are in the system.

    Args:
    - refnos (list or None): check specific reference numbers
    Returns:
    - Tuple of counts: fulfilled count, cancelled count, error count

    """

    gateway = PaymentGateway.get_gateway_class(ECOMMERCE_DEFAULT_PAYMENT_GATEWAY)

    if refnos is not None:
        pending_orders = PendingOrder.objects.filter(
            state=PendingOrder.STATE.PENDING, reference_number__in=refnos
        ).values_list("reference_number", flat=True)
    else:
        pending_orders = PendingOrder.objects.filter(
            state=PendingOrder.STATE.PENDING
        ).values_list("reference_number", flat=True)

    if len(pending_orders) == 0:
        return (0, 0, 0)

    log.info(f"Resolving {len(pending_orders)} orders")

    results = gateway.find_and_get_transactions(pending_orders)

    if len(results.keys()) == 0:
        log.info(f"No orders found to resolve.")
        return (0, 0, 0)

    fulfilled_count = cancel_count = error_count = 0

    for result in results:
        payload = results[result]
        if int(payload["reason_code"]) == 100:

            try:
                order = PendingOrder.objects.filter(
                    state=PendingOrder.STATE.PENDING,
                    reference_number=payload["req_reference_number"],
                ).get()

                order.fulfill(payload)
                order.save()
                fulfilled_count += 1

                log.info(f"Fulfilled order {order.reference_number}.")
            except Exception as e:
                log.error(
                    f"Couldn't process pending order for fulfillment {payload['req_reference_number']}: {str(e)}"
                )
                error_count += 1
        else:

            try:
                order = PendingOrder.objects.filter(
                    state=PendingOrder.STATE.PENDING,
                    reference_number=payload["req_reference_number"],
                ).get()

                order.cancel()
                order.transactions.create(
                    transaction_id=payload["transaction_id"],
                    amount=order.total_price_paid,
                    data=payload,
                    reason=f"Cancelled due to processor code {payload['reason_code']}",
                )
                order.save()
                cancel_count += 1

                log.info(f"Cancelled order {order.reference_number}.")
            except Exception as e:
                log.error(
                    f"Couldn't process pending order for cancellation {payload['req_reference_number']}: {str(e)}"
                )
                error_count += 1

    return (fulfilled_count, cancel_count, error_count)


def check_for_duplicate_discount_redemptions():
    """
    Checks for multiple redemptions for discount codes, and makes noise if there
    are any.

    For discounts that are one-time or one-time-per-user redemptions, there's a
    possibility that the code can be redeemed more than once. This will check
    for that and emit some log messages if so. (This can happen if the code is
    entered into two orders and those orders are completed simultaneously.)

    Returns:
    - List of seen discount IDs
    """

    redemptions = (
        DiscountRedemption.objects.filter(
            Q(redeemed_discount__redemption_type=REDEMPTION_TYPE_ONE_TIME)
            | Q(redeemed_discount__redemption_type=REDEMPTION_TYPE_ONE_TIME_PER_USER)
        )
        .filter(redeemed_order__state=Order.STATE.FULFILLED)
        .prefetch_related("redeemed_discount")
        .all()
    )

    seen = []

    for redemption in redemptions:
        if redemption.redeemed_discount.id in seen:
            continue

        if (
            redemption.redeemed_discount.redemption_type == REDEMPTION_TYPE_ONE_TIME
            and redemption.redeemed_discount.order_redemptions.filter(
                redeemed_order__state=Order.STATE.FULFILLED
            ).count()
            > 1
        ):
            message = f"Discount code {redemption.redeemed_discount.discount_code} is a one-time discount that's been redeemed more than once"
            log.error(message)
            seen.append(redemption.redeemed_discount.id)

        if (
            redemption.redeemed_discount.redemption_type
            == REDEMPTION_TYPE_ONE_TIME_PER_USER
            and redemption.redeemed_discount.order_redemptions.filter(
                redeemed_order__state=Order.STATE.FULFILLED
            ).count()
            > 1
        ):
            seen_user = []

            for (
                user_redemption
            ) in redemption.redeemed_discount.order_redemptions.filter(
                redeemed_order__state=Order.STATE.FULFILLED
            ).all():
                if user_redemption.redeemed_by.id in seen_user:
                    continue

                if (
                    redemption.redeemed_discount.order_redemptions.filter(
                        redeemed_by=user_redemption.redeemed_by
                    ).count()
                    > 1
                ):
                    message = f"Discount code {redemption.redeemed_discount.discount_code} is a one-time per-user discount that's been redeemed more than once by {user_redemption.redeemed_by}"
                    log.error(message)
                    seen_user.append(user_redemption.redeemed_by.id)

            seen.append(redemption.redeemed_discount.id)

    return seen


def generate_discount_code(**kwargs):
    """
    Generates a discount code (or a batch of discount codes) as specified by the
    arguments passed.

    Note that the prefix argument will not add any characters between it and the
    UUID - if you want one (the convention is a -), you need to ensure it's
    there in the prefix (and that counts against the limit)

    Keyword Args:
    * discount_type - one of the valid discount types
    * payment_type - one of the valid payment types
    * amount - the value of the discount
    * one_time - boolean; discount can only be redeemed once
    * one_time_per_user - boolean; discount can only be redeemed once per user
    * activates - date to activate
    * expires - date to expire the code
    * count - number of codes to create (requires prefix)
    * prefix - prefix to append to the codes (max 63 characters)

    Returns:
    * List of generated codes, with the following fields:
      code, type, amount, expiration_date

    """
    codes_to_generate = []
    discount_type = kwargs["discount_type"]
    redemption_type = REDEMPTION_TYPE_UNLIMITED
    payment_type = kwargs["payment_type"]
    amount = Decimal(kwargs["amount"])

    if kwargs["discount_type"] not in ALL_DISCOUNT_TYPES:
        raise Exception(f"Discount type {kwargs['discount_type']} is not valid.")

    if payment_type not in ALL_PAYMENT_TYPES:
        raise Exception(f"Payment type {payment_type} is not valid.")

    if kwargs["discount_type"] == DISCOUNT_TYPE_PERCENT_OFF and amount > 100:
        raise Exception(
            f"Discount amount {amount} not valid for discount type {DISCOUNT_TYPE_PERCENT_OFF}."
        )

    if kwargs["count"] > 1 and "prefix" not in kwargs:
        raise Exception("You must specify a prefix to create a batch of codes.")

    if kwargs["count"] > 1:
        prefix = kwargs["prefix"]

        # upped the discount code limit to 100 characters - this used to be 13 (50 - 37 for the UUID)
        if len(prefix) > 63:
            raise Exception(
                f"Prefix {prefix} is {len(prefix)} - prefixes must be 63 characters or less."
            )

        for i in range(0, kwargs["count"]):
            generated_uuid = uuid.uuid4()
            code = f"{prefix}{generated_uuid}"

            codes_to_generate.append(code)
    else:
        codes_to_generate = kwargs["codes"]

    if "one_time" in kwargs and kwargs["one_time"]:
        redemption_type = REDEMPTION_TYPE_ONE_TIME

    if "once_per_user" in kwargs and kwargs["once_per_user"]:
        redemption_type = REDEMPTION_TYPE_ONE_TIME_PER_USER

    if "expires" in kwargs and kwargs["expires"] is not None:
        expiration_date = parse_supplied_date(kwargs["expires"])
    else:
        expiration_date = None

    if "activates" in kwargs and kwargs["activates"] is not None:
        activation_date = parse_supplied_date(kwargs["activates"])
    else:
        activation_date = None

    generated_codes = []

    for code_to_generate in codes_to_generate:
        try:
            discount = Discount.objects.create(
                discount_type=discount_type,
                redemption_type=redemption_type,
                payment_type=payment_type,
                expiration_date=expiration_date,
                activation_date=activation_date,
                discount_code=code_to_generate,
                amount=amount,
            )

            generated_codes.append(discount)
        except:
            raise Exception(
                f"Discount code {code_to_generate} could not be created - maybe it already exists?"
            )

    return generated_codes
