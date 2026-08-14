"""Ecommerce APIs"""

import logging
import uuid
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urljoin

import stripe
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.urls import reverse
from ipware import get_client_ip
from mitol.common.utils.datetime import now_in_utc
from mitol.olposthog.features import is_enabled
from mitol.payment_gateway.api import CartItem as GatewayCartItem
from mitol.payment_gateway.api import Order as GatewayOrder
from mitol.payment_gateway.api import PaymentGateway, ProcessorResponse
from mitol.payment_gateway.constants import (
    MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
    MITOL_PAYMENT_GATEWAY_STRIPE,
)

from b2b.api import (
    get_active_contracts_from_basket_items,
    is_discount_supplied_for_b2b_purchase,
)
from courses.api import create_run_enrollments, deactivate_run_enrollment
from courses.constants import ENROLL_CHANGE_STATUS_REFUNDED
from courses.utils import is_uai_course_run
from ecommerce.constants import (
    ADMIN_FULFILLED_PAYMENT_DATA,
    ALL_DISCOUNT_TYPES,
    ALL_PAYMENT_TYPES,
    ALL_REDEMPTION_TYPES,
    CHECKOUT_CANCEL_ROUTE_MAP,
    CHECKOUT_SUCCESS_ROUTE_MAP,
    DISCOUNT_TYPE_PERCENT_OFF,
    PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
    PAYMENT_TYPE_SALES,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
    REFUND_SUCCESS_STATES,
    STRIPE_CHECKOUT_SESSION_STATUS_COMPLETE,
    STRIPE_CHECKOUT_SESSION_STATUS_OPEN,
    STRIPE_OVERALL_CHECKOUT_STATUS_CANCELLED,
    STRIPE_OVERALL_CHECKOUT_STATUS_ERROR,
    STRIPE_OVERALL_CHECKOUT_STATUS_PAID,
    STRIPE_OVERALL_CHECKOUT_STATUS_PENDING,
    STRIPE_OVERALL_CHECKOUT_STATUS_PENDING_ACTION,
    STRIPE_PAYMENT_INTENT_STATUS_CANCELLED,
    STRIPE_PAYMENT_INTENT_STATUS_PROCESSING,
    STRIPE_PAYMENT_INTENT_STATUS_SUCCEEDED,
    STRIPE_PAYMENT_STATUS_UNPAID,
    STRIPE_PAYMENT_STATUSES_GOOD,
    STRIPE_TRANSACTION_REASON_INITIAL_CHECKOUTSESSION,
    ZERO_PAYMENT_DATA,
)
from ecommerce.exceptions import (
    VerifiedProgramInvalidBasketError,
    VerifiedProgramInvalidOrderError,
    VerifiedProgramNoEnrollmentError,
)
from ecommerce.models import (
    Basket,
    BasketDiscount,
    BasketItem,
    Discount,
    DiscountProduct,
    DiscountRedemption,
    FulfilledOrder,
    Order,
    OrderStatus,
    PendingOrder,
    Product,
    StripeEventLog,
    UserDiscount,
)
from ecommerce.tasks import perform_downgrade_from_order
from flexiblepricing.api import determine_courseware_flexible_price_discount
from hubspot_sync.task_helpers import sync_hubspot_cart_add, sync_hubspot_deal
from main import features
from main.constants import (
    USER_MSG_TYPE_B2B_ERROR_MISSING_ENROLLMENT_CODE,
    USER_MSG_TYPE_B2B_INVALID_BASKET,
    USER_MSG_TYPE_BASKET_EMPTY,
    USER_MSG_TYPE_COURSE_NON_UPGRADABLE,
    USER_MSG_TYPE_DISCOUNT_INVALID,
    USER_MSG_TYPE_ENROLL_BLOCKED,
    USER_MSG_TYPE_ENROLL_DUPLICATED,
)
from main.utils import parse_supplied_date
from openedx.api import create_user
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE
from openedx.tasks import create_user_from_id

log = logging.getLogger(__name__)


def get_checkout_success_url(gateway_type):
    """Get the success endpoint for the gateway type."""

    if gateway_type not in CHECKOUT_SUCCESS_ROUTE_MAP:
        msg = f"Gateway {gateway_type} has no success route mapped"
        raise ValidationError(msg)

    return urljoin(
        settings.SITE_BASE_URL, reverse(CHECKOUT_SUCCESS_ROUTE_MAP[gateway_type])
    )


def get_checkout_cancel_url(gateway_type):
    """Get the cancel endpoint for the gateway type."""

    if gateway_type not in CHECKOUT_CANCEL_ROUTE_MAP:
        msg = f"Gateway {gateway_type} has no cancel route mapped"
        raise ValidationError(msg)

    return urljoin(
        settings.SITE_BASE_URL, reverse(CHECKOUT_CANCEL_ROUTE_MAP[gateway_type])
    )


def generate_checkout_payload(  # noqa: PLR0911, C901
    request, *, skip_discount_check=False, skip_receipt=False, gateway_type=None
):
    """
    Generate the checkout payload for the current basket.

    Set skip_discount_check when generating a payload for a verified program
    enrollment. The discount in that case is attached to the program, not the
    courserun that's being purchased, so it's technically "invalid".

    This will use the default configured gateway unless it is able to determine that the current user should use a specific gateway. This can be
    overridden by specifying gateway_type.

    Args:
    - request: the incoming http request
    Kwargs:
    - skip_discount_check: skip checking discounts for validity (default False)
    - skip_receipt: skip sending order receipt email (default False)
    - gateway_type: specify specific gateway type (default None)
    """

    from b2b.api import validate_basket_for_b2b_purchase  # noqa: PLC0415

    basket = establish_basket(request)

    if not gateway_type:
        global_id = request.user.global_id
        if global_id and is_enabled(
            features.STRIPE_ENABLE_FEATURE_FLAG,
            default=False,
            opt_unique_id=global_id,
        ):
            gateway_type = MITOL_PAYMENT_GATEWAY_STRIPE
        else:
            gateway_type = settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY

    if basket.has_user_blocked_products(request.user):
        return {
            "country_blocked": True,
            "error": USER_MSG_TYPE_ENROLL_BLOCKED,
        }

    if basket.has_user_purchased_same_courserun(request.user):
        return {
            "purchased_same_courserun": True,
            "error": USER_MSG_TYPE_ENROLL_DUPLICATED,
        }

    if basket.has_user_purchased_non_upgradable_courserun():
        return {
            "purchased_non_upgradeable_courserun": True,
            "error": USER_MSG_TYPE_COURSE_NON_UPGRADABLE,
        }

    if not skip_discount_check and not check_basket_discounts_for_validity(request):
        # We only allow one discount per basket so clear all of them here.
        basket.discounts.all().delete()
        apply_user_discounts(request)
        return {
            "invalid_discounts": True,
            "error": USER_MSG_TYPE_DISCOUNT_INVALID,
        }

    active_contracts = get_active_contracts_from_basket_items(basket)

    if not is_discount_supplied_for_b2b_purchase(request, active_contracts):
        return {
            "invalid_discounts": True,
            "error": USER_MSG_TYPE_B2B_ERROR_MISSING_ENROLLMENT_CODE,
        }

    if not validate_basket_for_b2b_purchase(request, active_contracts):
        return {
            "invalid_discounts": True,
            "error": USER_MSG_TYPE_B2B_INVALID_BASKET,
        }

    if not basket.basket_items.count():
        return {
            "basket_empty": True,
            "error": USER_MSG_TYPE_BASKET_EMPTY,
        }

    order = PendingOrder.create_from_basket(basket, gateway_type=gateway_type)
    total_price = 0

    ip = get_client_ip(request)[0]

    gateway_order = GatewayOrder(
        username=request.user.edx_username,
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
                order,
                payment_data=ZERO_PAYMENT_DATA,
                basket=basket,
                skip_receipt=skip_receipt,
            )

        order.refresh_from_db()

        return {
            "no_checkout": True,
            "order": order,
            "order_id": order.id,
        }

    payload = PaymentGateway.start_payment(
        gateway_type,
        gateway_order,
        get_checkout_success_url(gateway_type),
        get_checkout_cancel_url(gateway_type),
        merchant_fields=[basket.id],
    )

    if gateway_type == MITOL_PAYMENT_GATEWAY_STRIPE:
        # We will have gotten a CheckoutSession object from start_payment above.
        # This needs to be logged as a transaction, or we won't be able to find
        # this again in Stripe if something goes wrong after this step.
        order_flow = order.get_object_flow()
        order_flow.create_transaction(
            payload["payload"], reason=STRIPE_TRANSACTION_REASON_INITIAL_CHECKOUTSESSION
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
    """
    Checks the validity of the discounts in the basket against the user and
    the products in the basket.

    Returns:
        boolean: True if all discounts are valid, False otherwise.
    """
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

    # For multiple items, check each item for flexible pricing discounts
    basket_items = BasketItem.objects.filter(basket=basket)
    if basket_items.count() == 0:
        return

    # Use the first item's product for flexible pricing determination
    # This maintains backward compatibility while supporting multiple items
    product = basket_items.first().product
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


def fulfill_completed_order(
    order,
    payment_data,
    basket=None,
    already_enrolled=False,  # noqa: FBT002
    skip_receipt=False,  # noqa: FBT002
):
    order_flow = order.get_object_flow()
    order_flow.fulfill(
        payment_data, already_enrolled=already_enrolled, skip_receipt=skip_receipt
    )
    sync_hubspot_deal(order)

    if basket and basket.compare_to_order(order):
        basket.delete()


def get_order_from_cybersource_payment_response(request):
    payment_data = request.POST
    converted_order = PaymentGateway.get_gateway_class(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY
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
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
    ):
        raise PermissionDenied(
            "Could not validate response from the payment processor."  # noqa: EM101
        )

    processor_response = PaymentGateway.get_formatted_response(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
    )

    # Log message if reason_code is anything other than 100 (successful transaction)
    # only log 1xx as errors for now
    reason_code = processor_response.response_code
    transaction_id = processor_response.transaction_id
    if reason_code and reason_code.isdigit():
        reason_code = int(reason_code)
        message = "Transaction was not successful. Transaction ID:%s  Reason Code:%d  Message:%s"
        if 100 < reason_code < 200:  # noqa: PLR2004
            log.error(message, transaction_id, reason_code, processor_response.message)
        elif reason_code >= 200:  # noqa: PLR2004
            log.debug(message, transaction_id, reason_code, processor_response.message)

    return_message = ""

    if processor_response.state == ProcessorResponse.STATE_DECLINED:
        # Transaction declined for some reason
        # This probably means the order needed to go through the process
        # again so maybe tell the user to do a thing.
        log.debug(f"Transaction declined: {processor_response.message}")  # noqa: G004
        order_flow = order.get_object_flow()
        order_flow.decline()
        return_message = order.state
    elif processor_response.state == ProcessorResponse.STATE_ERROR:
        # Error - something went wrong with the request
        log.debug(
            f"Error happened submitting the transaction: {processor_response.message}"  # noqa: G004
        )
        order_flow = order.get_object_flow()
        order_flow.errored()
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
        log.debug(f"Transaction cancelled/reviewed: {processor_response.message}")  # noqa: G004
        order_flow = order.get_object_flow()
        order_flow.cancel()
        return_message = order.state

    elif (
        processor_response.state == ProcessorResponse.STATE_ACCEPTED
        or reason_code == 100  # noqa: PLR2004
    ):
        # It actually worked here
        basket = Basket.objects.filter(user=order.purchaser).first()
        try:
            log.debug(f"Transaction accepted!: {processor_response.message}")  # noqa: G004
            fulfill_completed_order(order, request.POST, basket)
        except ValidationError:
            log.debug(
                f"Missing transaction id from transaction response: {processor_response.message}"  # noqa: G004
            )
            raise

        return_message = order.state
    else:
        log.error(
            f"Unknown state {processor_response.state} found: transaction ID {transaction_id}, reason code {reason_code}, response message {processor_response.message}"  # noqa: G004
        )
        order_flow = order.get_object_flow()
        order_flow.cancel()
        return_message = order.state

    sync_hubspot_deal(order)
    return return_message


def establish_basket(request, *, no_delay=False):
    """
    Gets or creates the user's basket. Queue creation of their edX user if necessary.

    Kwargs:
        no_delay (bool): don't queue the edX user creation
    """
    user = request.user

    if not user.edx_username:
        if no_delay:
            create_user(user)
            # The openedx_user is a cached property, so delete the cached value
            del user.openedx_user
        else:
            create_user_from_id.delay(user.id)

    (basket, is_new) = Basket.objects.get_or_create(user=user)

    if is_new:
        basket.save()

    return basket


ANONYMOUS_BASKET_SESSION_KEY = "anonymous_basket_id"


def get_anonymous_basket_id(request, *, create=False):
    """
    Get the anonymous basket id stored in the request's session, minting one
    if requested and none exists yet.

    Kwargs:
        create (bool): mint and store a new id in the session if one isn't
            already present. Only pass True from call sites that are about to
            write to the basket - minting an id writes to the session, which
            forces a Set-Cookie header and defeats caching for anonymous page
            views that don't need one.
    """
    anonymous_id = request.session.get(ANONYMOUS_BASKET_SESSION_KEY)

    if anonymous_id is None and create:
        anonymous_id = str(uuid.uuid4())
        request.session[ANONYMOUS_BASKET_SESSION_KEY] = anonymous_id

    return anonymous_id


def establish_basket_for_request(request, *, for_update=False):
    """
    Get or create the basket for the current request, whether the requester
    is authenticated or anonymous.

    Kwargs:
        for_update (bool): re-fetch the basket with select_for_update() so it's
            locked for the remainder of the caller's transaction. Pass True
            when the caller is about to mutate basket contents.
    """
    if request.user.is_authenticated:
        basket = establish_basket(request)
    else:
        anonymous_id = get_anonymous_basket_id(request, create=True)
        basket, _ = Basket.objects.get_or_create(anonymous_id=anonymous_id)

    if for_update:
        basket = Basket.objects.select_for_update().get(pk=basket.pk)

    return basket


def claim_anonymous_basket(request):
    """
    Convert the anonymous basket identified by the current session into a
    basket for the now-authenticated request.user.

    If request.user already has a basket, it is discarded in favor of the
    anonymous basket - the anonymous basket reflects what was just shown on
    the cart page, and merging would silently change the price the user saw.

    Returns the claimed basket, or None if there's no anonymous basket to
    claim (e.g. an expired session).
    """
    anonymous_id = get_anonymous_basket_id(request, create=False)
    if anonymous_id is None:
        return None

    with transaction.atomic():
        try:
            anon_basket = Basket.objects.select_for_update().get(
                anonymous_id=anonymous_id
            )
        except Basket.DoesNotExist:
            return None

        Basket.objects.filter(user=request.user).exclude(pk=anon_basket.pk).delete()

        anon_basket.user = request.user
        anon_basket.anonymous_id = None
        anon_basket.save(update_fields=["user", "anonymous_id"])

    del request.session[ANONYMOUS_BASKET_SESSION_KEY]
    apply_user_discounts(request)

    return anon_basket


def cull_anonymous_baskets():
    """
    Delete anonymous baskets that haven't been touched in a while (abandoned
    carts). A basket's anonymous_id is only reachable via its session cookie,
    so once that cookie could plausibly have expired there's no way for a
    basket to ever be claimed - it's safe to remove.
    """
    cutoff = now_in_utc() - timedelta(seconds=settings.ANONYMOUS_BASKET_CULL_AGE)

    Basket.objects.filter(anonymous_id__isnull=False, updated_on__lt=cutoff).delete()


def refund_order(*, order_id: int = None, reference_number: str = None, **kwargs):  # noqa: RUF013
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
    message = ""
    if reference_number is not None:
        order = FulfilledOrder.objects.get(reference_number=reference_number)
    elif order_id is not None:
        order = FulfilledOrder.objects.get(pk=order_id)
    else:
        message = "Either order_id or reference_number is required to fetch the Order."
        log.error(message)
        return False, message
    if order.state != OrderStatus.FULFILLED:
        message = f"Order with order_id {order.id} is not in fulfilled state."
        log.error(message)
        return False, message

    order_recent_transaction = order.transactions.first()

    if not order_recent_transaction:
        message = f"There is no associated transaction against order_id {order.id}"
        log.error(message)
        return False, message

    transaction_dict = order_recent_transaction.data

    # Check for a PayPal payment - if there's one, we can't process it
    if "paypal_token" in transaction_dict:
        raise Exception(  # noqa: TRY002
            f"PayPal: Order {order.reference_number} contains a PayPal transaction. Please contact Finance to refund this order."  # noqa: EM102
        )

    # The refund amount can be different then the payment amount, so we override
    # that before PaymentGateway processing.
    # e.g. While refunding order from Django Admin we can select custom amount.
    if refund_amount:
        transaction_dict["req_amount"] = refund_amount

    refund_gateway_request = PaymentGateway.create_refund_request(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, transaction_dict
    )

    response = PaymentGateway.start_refund(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,
        refund_gateway_request,
    )

    if response.state in REFUND_SUCCESS_STATES:
        # Record refund transaction with PaymentGateway's refund response
        order_flow = order.get_object_flow()
        order_flow.refund(
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
        raise Exception(f"Payment gateway returned an error: {response.message}")  # noqa: EM102, TRY002

    # If unenroll requested, perform unenrollment after successful refund
    if unenroll:
        perform_downgrade_from_order.delay(order.id)

    return True, message


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
            except ObjectDoesNotExist:  # noqa: PERF203
                pass


def _retrieve_pending_cybersource_orders(orders):
    """
    Retrieve the current status for CyberSource Secure Acceptance orders.

    For these, we look up the CyberSource order info in a batch and then sort
    them into buckets for further processing.
    """

    completed = {}
    cancelled = {}

    order_refnos = [order.reference_number for order in orders]
    gateway = PaymentGateway.get_gateway_class(MITOL_PAYMENT_GATEWAY_CYBERSOURCE)

    results = gateway.find_and_get_transactions(order_refnos)

    if len(results.keys()) == 0:
        log.info("_retrieve_pending_cybersource_orders: No orders found to resolve.")
        return (
            completed,
            cancelled,
        )

    for _, payload in results.items():
        if int(payload["reason_code"]) == 100:  # noqa: PLR2004
            completed[payload["req_reference_number"]] = payload
        else:
            cancelled[payload["req_reference_number"]] = payload

    return (
        completed,
        cancelled,
    )


def _retrieve_pending_stripe_orders(orders):
    """
    Retrieve current status for Stripe orders.

    Stripe doesn't have a batch list, so retrieve status individually, and sort
    into the same buckets as _retrieve_pending_cybersource_orders. We must have
    a CheckoutSession stored for the order to be able to look it up later.
    """

    completed = {}
    cancelled = {}
    gateway = PaymentGateway.get_gateway_class(MITOL_PAYMENT_GATEWAY_STRIPE)

    # We should be logging the initial checkout session in a specific way
    # (see generate_checkout_payload) so we can find those transactions for the
    # order. If there's not one then we skip it, so maybe it can be picked up
    # later in event processing.

    for order in orders:
        checkout_session_transactions = order.transactions.filter(
            reason=STRIPE_TRANSACTION_REASON_INITIAL_CHECKOUTSESSION
        )

        if not checkout_session_transactions.exists():
            log.info(
                "Order %s (ref %s) has no apparant CheckoutSession logged.",
                order.id,
                order.reference_number,
            )
            continue

        session_transaction = checkout_session_transactions.first()
        checkout_session_id = session_transaction.data.get("id")

        if (
            session_transaction.data.get("object") != "checkout.session"
            or not checkout_session_id
        ):
            log.info(
                "Order %s (ref %s) has no apparant CheckoutSession logged.",
                order.id,
                order.reference_number,
            )
            continue

        checkout_session = process_stripe_checkout_session_status(checkout_session_id)

        if checkout_session["status"] == "cancelled":
            cancelled[order.reference_number] = checkout_session["transaction"]
        elif checkout_session["status"] == "paid":
            completed[order.reference_number] = checkout_session["transaction"]

    return (
        completed,
        cancelled,
    )


def check_and_process_pending_orders_for_resolution(
    refnos: list[str], *, check_status: bool = True, skip_fulfillment: bool = False
):
    """
    Checks pending orders for resolution. By default, this will pull all the
    pending orders that are in the system.

    Args:
    - refnos: list of reference numbers to check - empty list to check all Pending
    Keyword Args:
    - check_status: get the status of the order from the payment processor (default True)
    - skip_fulfillment: don't fulfill the order, just mark it as Fulfilled
    Returns:
    - Tuple of counts: fulfilled count, cancelled count, error count

    """

    fulfilled_count = cancel_count = error_count = 0

    if len(refnos) > 0:
        pending_orders = PendingOrder.objects.filter(
            state=OrderStatus.PENDING, reference_number__in=refnos
        )
    else:
        pending_orders = PendingOrder.objects.filter(state=OrderStatus.PENDING)

    if len(pending_orders) == 0:
        return (0, 0, 0)

    log.info("Resolving %s orders", len(pending_orders))

    # TODO: get the stripe part of this fleshed out

    if check_status:
        cs_gateway_orders = [
            pending_order
            for pending_order in pending_orders
            if pending_order.gateway_type == MITOL_PAYMENT_GATEWAY_CYBERSOURCE
        ]
        stripe_gateway_orders = [
            pending_order
            for pending_order in pending_orders
            if pending_order.gateway_type == MITOL_PAYMENT_GATEWAY_STRIPE
        ]

        cs_success, cs_cancel = _retrieve_pending_cybersource_orders(cs_gateway_orders)
        stripe_success, stripe_cancel = _retrieve_pending_stripe_orders(
            stripe_gateway_orders
        )

        success_orders = {**cs_success, **stripe_success}
        cancel_orders = {**cs_cancel, **stripe_cancel}
    else:
        cancel_orders = {}
        success_orders = {}
        for order in pending_orders:
            success_orders[order.reference_number] = ADMIN_FULFILLED_PAYMENT_DATA

    for refno, payload in success_orders.items():
        try:
            order = PendingOrder.objects.filter(
                state=OrderStatus.PENDING,
                reference_number=refno,
            ).get()
            order_flow = order.get_object_flow()
            order_flow.fulfill(payload, skip_fulfillment=skip_fulfillment)
            sync_hubspot_deal(order)
            fulfilled_count += 1

            log.info("Fulfilled order %s.", order.reference_number)
        except Exception:  # noqa: PERF203
            log.exception(
                "Couldn't process pending order for fulfillment %s",
                refno,
            )
            error_count += 1

    for refno, payload in cancel_orders.items():
        try:
            order = PendingOrder.objects.filter(
                state=OrderStatus.PENDING,
                reference_number=refno,
            ).get()
            order_flow = order.get_object_flow()
            order_flow.cancel(api_response_data=payload)
            sync_hubspot_deal(order)
            cancel_count += 1

            log.info("Cancelled order %s.", order.reference_number)
        except Exception:  # noqa: PERF203
            log.exception(
                "Couldn't process pending order for cancellation %s",
                refno,
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
        .filter(redeemed_order__state=OrderStatus.FULFILLED)
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
                redeemed_order__state=OrderStatus.FULFILLED
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
                redeemed_order__state=OrderStatus.FULFILLED
            ).count()
            > 1
        ):
            seen_user = []

            for (
                user_redemption
            ) in redemption.redeemed_discount.order_redemptions.filter(
                redeemed_order__state=OrderStatus.FULFILLED
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


def generate_discount_code(**kwargs):  # noqa: C901
    """
    Generates a discount code (or a batch of discount codes) as specified by the
    arguments passed.

    Note that the prefix argument will not add any characters between it and the
    UUID - if you want one (the convention is a -), you need to ensure it's
    there in the prefix (and that counts against the limit)

    If you specify redemption_type, specifying one_time or one_time_per_user will not be
    honored.

    Keyword Args:
    * discount_type - one of the valid discount types
    * payment_type - one of the valid payment types
    * redemption_type - one of the valid redemption types (overrules use of the flags)
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
        raise Exception(f"Discount type {kwargs['discount_type']} is not valid.")  # noqa: EM102, TRY002

    if payment_type not in ALL_PAYMENT_TYPES:
        raise Exception(f"Payment type {payment_type} is not valid.")  # noqa: EM102, TRY002

    if kwargs["discount_type"] == DISCOUNT_TYPE_PERCENT_OFF and amount > 100:  # noqa: PLR2004
        raise Exception(  # noqa: TRY002
            f"Discount amount {amount} not valid for discount type {DISCOUNT_TYPE_PERCENT_OFF}."  # noqa: EM102
        )

    if kwargs["count"] > 1 and "prefix" not in kwargs:
        raise Exception("You must specify a prefix to create a batch of codes.")  # noqa: EM101, TRY002

    if kwargs["count"] > 1:
        prefix = kwargs["prefix"]

        # upped the discount code limit to 100 characters - this used to be 13 (50 - 37 for the UUID)
        if len(prefix) > 63:  # noqa: PLR2004
            raise Exception(  # noqa: TRY002
                f"Prefix {prefix} is {len(prefix)} - prefixes must be 63 characters or less."  # noqa: EM102
            )

        for i in range(kwargs["count"]):  # noqa: B007
            generated_uuid = uuid.uuid4()
            code = f"{prefix}{generated_uuid}"

            codes_to_generate.append(code)
    else:
        codes_to_generate = kwargs["codes"]

    if kwargs.get("one_time"):
        redemption_type = REDEMPTION_TYPE_ONE_TIME

    if kwargs.get("once_per_user"):
        redemption_type = REDEMPTION_TYPE_ONE_TIME_PER_USER

    if (
        "redemption_type" in kwargs
        and kwargs["redemption_type"] in ALL_REDEMPTION_TYPES
    ):
        redemption_type = kwargs["redemption_type"]

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
        discount = Discount.objects.create(
            discount_type=discount_type,
            redemption_type=redemption_type,
            payment_type=payment_type,
            expiration_date=expiration_date,
            activation_date=activation_date,
            discount_code=code_to_generate,
            amount=amount,
            is_bulk=True,
        )

        generated_codes.append(discount)

    return generated_codes


def get_auto_apply_discounts_for_basket(basket_id: int) -> QuerySet[Discount]:
    """
    Get the auto-apply discounts that can be applied to a basket.

    This includes the financial assistant discounts for the user and products,
    if there are any, since those are also automatically applied regardless of
    the flag on the discount. This does not include B2B discounts because those
    are applied in a different manner - either through a separate API, or by the
    learner via the cart interface.

    Args:
        basket_id (int): The ID of the basket to get the auto-apply discounts for.

    Returns:
        QuerySet: The auto-apply discounts that can be applied to the basket.
    """
    basket = Basket.objects.get(pk=basket_id)
    products = basket.get_products()

    finaid_discounts = []

    for product in products:
        finaid_discount = determine_courseware_flexible_price_discount(
            product, basket.user
        )

        if finaid_discount:
            finaid_discounts.append(finaid_discount.id)

    return Discount.objects.filter(
        Q(activation_date__lte=now_in_utc()) | Q(activation_date=None),
        Q(expiration_date__gt=now_in_utc()) | Q(expiration_date=None),
    ).filter(
        Q(user_discount_discount__user=basket.user)
        | Q(pk__in=finaid_discounts)
        | Q(automatic=True)
    )


def apply_discount_to_basket(basket: Basket, discount: Discount, *, allow_finaid=False):  # noqa: C901
    """
    Apply a discount to a basket.

    Discount application is subject to rules:
    - The discount itself must be valid on its face (not inactive, applies to products, etc.)
    - The discount is not a financial assistance tier discount, unless allow_finaid is set
    - The discount provides a better price to the learner than any other applied discount
    - The discount is not overriding a user discount

    If a user discount is supplied to this function, then that discount will be
    applied _unless_ a financial assistance discount is also applied. User
    discounts take precedence over any other discount, other than financial
    assistance discounts.

    This function is not for use with B2B or verified program enrollment code
    redemption. Those use cases have their own redemption code paths because
    they need different verification steps.

    Args:
        discount (Discount): The Discount to apply to the basket.
    Keyword Args:
        allow_finaid (bool): Allow a financial assistance discount through.
    """
    if discount.is_valid(basket, allow_finaid=allow_finaid):
        defaults = {
            "redeemed_discount": discount,
            "redemption_date": now_in_utc(),
        }

        if basket.discounts.count() > 0 and basket.basket_items.count() > 0:
            # Check to make sure the supplied discount can be applied. This means
            # that it should not override any user discounts that are applied,
            # and it should be better than the other discounts in the basket.

            if discount.user_discount_discount.filter(user=basket.user).exists():
                # This is a user discount.
                # Check for an existing tier discount - user discount shouldn't override that
                finaid_discounts = [
                    basket_discount
                    for basket_discount in basket.discounts.all()
                    if basket_discount.redeemed_discount.flexible_price_tiers.count()
                    > 0
                ]

                if len(finaid_discounts) > 0:
                    # There is a finaid discount, so don't apply this user one.
                    return
            else:
                is_finaid_discount = discount.flexible_price_tiers.exists()
                has_user_discount = (
                    basket.discounts.filter(
                        redeemed_discount__user_discount_discount__user=basket.user
                    ).count()
                    > 0
                )

                if is_finaid_discount and not allow_finaid:
                    # Financial assistance discount; bail unless the flag is set
                    return

                if has_user_discount and is_finaid_discount and allow_finaid:
                    # Basket has a user discount applied; this is a finaid
                    # discount (and we're allowed to apply it); apply the
                    # discount without further evaluation.

                    BasketDiscount.objects.update_or_create(
                        redeemed_by=basket.user,
                        redeemed_basket=basket,
                        defaults=defaults,
                        create_defaults=defaults,
                    )
                    return

                if has_user_discount:
                    # This basket has a user discount applied; this isn't a
                    # finaid discount that we're permitting to be applied; so
                    # skip this one.
                    return

                found_better = False

                for item in basket.basket_items.all():
                    test_price = discount.discount_product(item.product, basket.user)
                    if test_price and item.discounted_price >= test_price:
                        found_better = True
                        break

                if not found_better:
                    return

        BasketDiscount.objects.update_or_create(
            redeemed_by=basket.user,
            redeemed_basket=basket,
            defaults=defaults,
            create_defaults=defaults,
        )


def create_verified_program_discount(program):
    """
    Create discount (enrollment) codes for a program.

    When a learner buys a program, they need to be able to get verified enrollments
    in the courses that are in the program. We generally do this with enrollment
    codes - this creates one for the program that is set up to make the order
    zero-value, so the learner doesn't have to pay for upgraded enrollments.

    This will create a single discount, with the "verified program" flag set,
    with unlimited redemptions, set to 100% off.

    If a discount already exists for this purpose, this will return it.

    Args:
    - program (Program): the program to create a discount for
    Returns:
    - Discount, the discount that was created
    """

    content_type = ContentType.objects.get_for_model(program)
    product = Product.objects.filter(
        content_type=content_type, object_id=program.id
    ).get()

    existing_discount_qs = Discount.objects.filter(
        Q(activation_date__isnull=True) | Q(activation_date__lte=now_in_utc()),
        Q(expiration_date__isnull=True) | Q(expiration_date__gte=now_in_utc()),
        products__product=product,
        is_program_discount=True,
    )

    if existing_discount_qs.exists():
        return existing_discount_qs.last()

    discount = Discount.objects.create(
        amount=Decimal(100),
        automatic=False,
        discount_type=DISCOUNT_TYPE_PERCENT_OFF,
        redemption_type=REDEMPTION_TYPE_UNLIMITED,
        payment_type=PAYMENT_TYPE_SALES,
        discount_code=f"{program.readable_id}-{uuid.uuid4()}",
        is_bulk=True,
        is_program_discount=True,
    )

    DiscountProduct.objects.create(discount=discount, product=product)

    return discount


def create_verified_program_course_run_enrollment(request, courserun, program):
    """
    Create a verified course run enrollment in a course that is associated with
    a program for the specified learner.

    If the learner has a verified enrollment in the program, and they're enrolling
    in a course run that's for a course within the program, they'll need a
    matching verified enrollment in the course run too. We want verified
    enrollments to have corresponding orders within the system. So, this takes
    the user, run, and program and creates an order and fulfills it.

    Because the learner has already paid for the program, though, we need to make
    sure they're not paying for the run again. So, the order should be a
    zero-value one. This will use a discount code for this - if we don't have one
    already, then we will make one on the fly for the program, and then apply it
    to the order.

    Courses can belong to multiple programs, so the program must be specified
    so the function can verify the user's program enrollment.

    Args:
    - request: The incoming HTTP request.
    - courserun: The course run to purchase.
    - program: The program to use.
    Returns:
    - CourseRunEnrollment
    Raises:
    - VerifiedProgramNoEnrollmentError if the learner doesn't have a program
      enrollment
    - VerifiedProgramInvalidBasketError if the basket isn't zero value
    - VerifiedProgramInvalidOrderError if the order doesn't get processed through
    """

    if not program.enrollments.filter(
        user=request.user, enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE, active=True
    ).exists():
        msg = f"No verified enrollment for {request.user} for program {program}"
        raise VerifiedProgramNoEnrollmentError(msg)

    discount = create_verified_program_discount(program)

    cr_ctype = ContentType.objects.get_for_model(courserun)
    product = Product.objects.filter(
        content_type=cr_ctype, object_id=courserun.id, is_active=True
    ).get()

    basket = establish_basket(request)

    if basket.basket_items.count() > 0:
        # Stuff in the basket - clear it out first.
        basket.basket_items.all().delete()
        basket.discounts.all().delete()

    BasketItem.objects.create(basket=basket, product=product, quantity=1)
    BasketDiscount.objects.create(
        redemption_date=now_in_utc(),
        redeemed_by=request.user,
        redeemed_discount=discount,
        redeemed_basket=basket,
    )

    # Sync with HubSpot for CourseRun and Program products
    sync_hubspot_cart_add(
        request.user, product, is_uai=(is_uai_course_run(product.purchasable_object))
    )

    if Decimal(
        sum([basket_item.discounted_price for basket_item in basket.basket_items.all()])
    ) > Decimal(0):
        # For some reason the basket's not zero-value.
        msg = f"Basket for {request.user} is not zero-value"
        raise VerifiedProgramInvalidBasketError(msg)

    processed_order = generate_checkout_payload(
        request, skip_discount_check=True, skip_receipt=True
    )

    if "no_checkout" not in processed_order:
        # It didn't just clear the order so something went wrong
        raise VerifiedProgramInvalidOrderError

    return courserun.enrollments.filter(user=request.user).get()


def log_stripe_event(event, *, order: Order | None = None):
    """Log a Stripe event."""

    return StripeEventLog.objects.create(
        event_id=event.id, event_data=event.to_dict(for_json=True), related_order=order
    )


def process_stripe_checkout_session_event(event: stripe.Event):
    """
    Process the Stripe event passed.

    This validates that the event is a CheckoutSession event and strips the
    CheckoutSession object out of the event.
    """

    valid_types = [
        "checkout.session.completed",
        "checkout.session.expired",
        "checkout.session.async_payment_failed",
        "checkout.session.async_payment_succeeded",
    ]

    ev_type = event.type
    if ev_type not in valid_types:
        msg = f"Event passed to process_stripe_checkout_session_event is type {ev_type} - not a checkout session event"
        raise ValueError(msg)

    return event.data.object


def _get_stripe_checkout_session_v1():
    """Return the checkout session v1 client (mostly to make testing easier)."""

    stripe_gateway = PaymentGateway.get_gateway_class(MITOL_PAYMENT_GATEWAY_STRIPE)
    return stripe_gateway.stripe_client.v1.checkout.sessions


def process_stripe_checkout_session_status(checkout_session: dict | str):
    """
    Process the provided Stripe CheckoutSession and provide its status.

    The CheckoutSession has some status fields in it, but we also need to look
    at the PaymentIntent to get the status of the payment itself. This will
    re-pull the session from the API with expand turned on for PaymentIntent so
    we get that data. (As is the PaymentGateway calls don't use expand, so there
    would have needed to be an additional API call to get the PaymentIntent
    anyway.)

    Args:
    - checkout_session (dict|str): either a CheckoutSession (as a dict), or the
      ID of the checkout session to pull
    Returns:
    - something, dunno yet
    """

    stripe_checkout_session_client = _get_stripe_checkout_session_v1()

    if isinstance(checkout_session, dict):
        session_id = checkout_session.get("id")
    else:
        session_id = checkout_session

    if not session_id:
        msg = "checkout session ID not found"
        raise ValueError(msg)

    # Call this directly so we can tell the client to expand payment_intent.

    cs = stripe_checkout_session_client.retrieve(
        session_id,
        {
            "expand": [
                "payment_intent",
            ],
        },
    )

    breakpoint()

    # The session itself has two status fields: status and payment_status
    # status is the session status - open, complete, expired
    # payment_status is payment with relation to the session - no_payment_required, paid, unpaid
    # The PaymentIntent (if it exists) has the status of whatever actual payment
    # was received. If cancelled, it also has a cancellation reason.

    session_status = {
        "status": STRIPE_OVERALL_CHECKOUT_STATUS_PENDING,
        "cancel_reason": "",
        "action_reason": "",
        "checkout_session_id": cs.id,
        "payment_intent_id": "",
        "transaction": cs.to_dict(for_json=True),
    }

    if not cs.payment_intent:
        if cs.status == STRIPE_CHECKOUT_SESSION_STATUS_OPEN or (
            cs.status == STRIPE_CHECKOUT_SESSION_STATUS_COMPLETE
            and cs.payment_status == STRIPE_PAYMENT_STATUS_UNPAID
        ):
            session_status["status"] = STRIPE_OVERALL_CHECKOUT_STATUS_PENDING
        elif cs.status == STRIPE_CHECKOUT_SESSION_STATUS_COMPLETE and (
            cs.payment_status in STRIPE_PAYMENT_STATUSES_GOOD
        ):
            # "complete" and "paid" is a weird state - we should have a PaymentIntent
            session_status["status"] = STRIPE_OVERALL_CHECKOUT_STATUS_PAID
        elif (
            cs.status == "expired" and cs.payment_status == STRIPE_PAYMENT_STATUS_UNPAID
        ):
            session_status["status"] = STRIPE_OVERALL_CHECKOUT_STATUS_CANCELLED
            session_status["cancel_reason"] = "expired-unpaid"
        else:
            # weird state again - expired and paid or expired and no-payment-required

            log.warning(
                "Checkout session %s in weird state: state %s and payment_state %s",
                cs.id,
                cs.status,
                cs.payment_status,
            )
            session_status["status"] = STRIPE_OVERALL_CHECKOUT_STATUS_PENDING

        return session_status

    pi = cs.payment_intent
    session_status["payment_intent_id"] = pi.id

    if pi.status == STRIPE_PAYMENT_INTENT_STATUS_PROCESSING:
        session_status["status"] = STRIPE_OVERALL_CHECKOUT_STATUS_PENDING
    elif pi.status == STRIPE_PAYMENT_INTENT_STATUS_SUCCEEDED:
        session_status["status"] = STRIPE_OVERALL_CHECKOUT_STATUS_PAID
    elif pi.status == STRIPE_PAYMENT_INTENT_STATUS_CANCELLED:
        session_status["status"] = STRIPE_OVERALL_CHECKOUT_STATUS_CANCELLED
        session_status["cancel_reason"] = pi.cancellation_reason
    else:
        session_status["status"] = STRIPE_OVERALL_CHECKOUT_STATUS_PENDING_ACTION
        session_status["action_reason"] = pi.status

    return session_status


def process_stripe_checkout_completed(event):
    """Process the checkout completed event."""

    checkout_session = process_stripe_checkout_session_event(event)

    order_reference_number = checkout_session.client_reference_id
    session_id = checkout_session.id
    status_obj = process_stripe_checkout_session_status(checkout_session.id)

    log.debug(
        "process_stripe_checkout_completed: processing event %s for checkout session %s (order %s)in overall state %s",
        event.id,
        session_id,
        order_reference_number,
        status_obj["status"],
    )

    order = Order.objects.filter(reference_number=order_reference_number).first()

    StripeEventLog.objects.filter(event_id=event.id).update(related_order=order)

    if not order:
        log.error(
            "process_stripe_checkout_completed: session %s for order %s has no matching order",
            session_id,
            order_reference_number,
        )

        return False

    if status_obj["status"] in [
        STRIPE_OVERALL_CHECKOUT_STATUS_CANCELLED,
        STRIPE_OVERALL_CHECKOUT_STATUS_ERROR,
    ]:
        log.info(
            "process_stripe_checkout_completed: session %s for order %s ended unsuccessfully: %s - %s",
            session_id,
            order_reference_number,
            status_obj["status"],
            status_obj["cancel_reason"],
        )

        order.get_object_flow().errored(api_response_data=event.to_dict(for_json=True))
        order.refresh_from_db()
    elif status_obj["status"] in [
        STRIPE_OVERALL_CHECKOUT_STATUS_PENDING,
        STRIPE_OVERALL_CHECKOUT_STATUS_PENDING_ACTION,
    ]:
        log.info(
            "process_stripe_checkout_completed: session %s for order %s is still in pending state: %s - %s",
            session_id,
            order_reference_number,
            status_obj["status"],
            status_obj["action_reason"],
        )
    else:
        basket = Basket.objects.filter(user=order.purchaser).first()

        fulfill_completed_order(order, event.to_dict(for_json=True), basket)

        order.refresh_from_db()

    return order


def process_stripe_checkout_expired(event):
    """
    Process the checkout expired event.

    Checkout sessions last for a finite amount of time; if the user doesn't
    complete checkout in enough time, it will expire and we'll need to cancel
    the order. This does less procesing than the completed webhook; we can use
    the event type as the order state.
    """

    checkout_session = process_stripe_checkout_session_event(event)

    order_reference_number = checkout_session.client_reference_id
    session_id = checkout_session.id

    log.debug(
        "process_stripe_checkout_expired: processing event %s for checkout session %s (order %s)",
        event.id,
        session_id,
        order_reference_number,
    )
    log.warning(
        "process_stripe_checkout_expired: checkout session %s for order %s expired - cancelling the in-flight order",
        session_id,
        order_reference_number,
    )

    order = Order.objects.filter(reference_number=order_reference_number).get()
    StripeEventLog.objects.filter(event_id=event.id).update(related_order=order)

    order.get_object_flow().cancel(api_response_data=event.to_dict(for_json=True))

    order.refresh_from_db()
    return order
