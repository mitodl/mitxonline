"""
MITxOnline ecommerce views
"""
import logging
from rest_framework import mixins, status
from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView
from rest_framework.viewsets import ReadOnlyModelViewSet, GenericViewSet, ViewSet
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from ipware import get_client_ip

from django.views.generic import TemplateView
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin

from django.db.models import Q, Count
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied

from reversion.models import Version
from django.urls import reverse
from main.settings import ECOMMERCE_DEFAULT_PAYMENT_GATEWAY
from main import features

from mitol.common.utils import now_in_utc
from rest_framework_extensions.mixins import NestedViewSetMixin
from mitol.payment_gateway.api import (
    CartItem as GatewayCartItem,
    Order as GatewayOrder,
    PaymentGateway,
    CyberSourcePaymentGateway,
    ProcessorResponse,
)

from courses.models import (
    CourseRun,
    Course,
    Program,
    ProgramRun,
)

from ecommerce.serializers import (
    ProductSerializer,
    BasketSerializer,
    BasketItemSerializer,
    BasketWithProductSerializer,
    OrderSerializer,
)

log = logging.getLogger(__name__)
from ecommerce.models import (
    Product,
    Basket,
    BasketItem,
    Discount,
    BasketDiscount,
    PendingOrder,
    Order,
    Line,
)
from ecommerce.discounts import DiscountType


class ProductsPagination(LimitOffsetPagination):
    default_limit = 2
    limit_query_param = "l"
    offset_query_param = "o"
    max_limit = 50


class ProductViewSet(ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    pagination_class = ProductsPagination

    def get_queryset(self):
        now = now_in_utc()

        unenrollable_courserun_ids = CourseRun.objects.filter(
            enrollment_end__lt=now
        ).values_list("id", flat=True)

        unenrollable_course_ids = (
            Course.objects.annotate(
                num_runs=Count(
                    "courseruns", filter=~Q(courseruns__in=unenrollable_courserun_ids)
                )
            )
            .filter(num_runs=0)
            .values_list("id", flat=True)
        )

        unenrollable_program_ids = (
            Program.objects.annotate(
                valid_runs=Count(
                    "programruns",
                    filter=Q(programruns__end_date__gt=now)
                    | Q(programruns__end_date=None),
                )
            )
            .filter(
                Q(programruns__isnull=True)
                | Q(valid_runs=0)
                | Q(courses__in=unenrollable_course_ids)
            )
            .values_list("id", flat=True)
            .distinct()
        )

        unenrollable_programrun_ids = ProgramRun.objects.filter(
            Q(program__in=unenrollable_program_ids) | Q(end_date__lt=now)
        )

        return (
            Product.objects.exclude(
                (
                    Q(object_id__in=unenrollable_courserun_ids)
                    & Q(content_type__model="courserun")
                )
                | (
                    Q(object_id__in=unenrollable_programrun_ids)
                    & Q(content_type__model="programrun")
                )
            )
            .exclude(is_active__exact=False)
            .select_related("content_type")
            .prefetch_related("purchasable_object")
        )


class BasketViewSet(
    NestedViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    """API view set for Basket"""

    serializer_class = BasketSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "user__username"
    lookup_url_kwarg = "username"

    def get_object(self, username=None):
        basket, _ = Basket.objects.get_or_create(user=self.request.user)
        return basket

    def get_queryset(self):
        return Basket.objects.filter(user=self.request.user).all()


class BasketItemViewSet(
    NestedViewSetMixin, ListCreateAPIView, mixins.DestroyModelMixin, GenericViewSet
):
    """API view set for BasketItem"""

    serializer_class = BasketItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BasketItem.objects.filter(basket__user=self.request.user)

    def create(self, request, *args, **kwargs):
        basket = Basket.objects.get(user=request.user)
        product_id = request.data.get("product")
        serializer = self.get_serializer(
            data={"product": product_id, "basket": basket.id}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


def generate_checkout_payload(request):
    basket = Basket.objects.filter(user=request.user).get()

    discounts = BasketDiscount.objects.filter(redeemed_basket=basket).all()

    total = 0

    order = PendingOrder(total_price_paid=0, purchaser=request.user)
    order.save()

    ip = get_client_ip(request)[0]

    gateway_order = GatewayOrder(
        username=request.user.username,
        ip_address=ip,
        reference=order.reference_number,
        items=[],
    )

    for lineitem in basket.basket_items.all():
        line_item_price = lineitem.product.price

        if len(discounts) > 0:
            for discount in discounts:
                discount_cls = DiscountType.for_discount(discount.discount_type)
                discounted_price = discount_cls.get_product_price(lineitem.product)
                total += discounted_price
                line_item_price = discounted_price
        else:
            total += lineitem.product.price

        product_version = Version.objects.get_for_object(lineitem.product).first()
        Line(order=order, product_version=product_version, quantity=1).save()
        gateway_order.items.append(
            GatewayCartItem(
                code=product_version.field_dict["content_type_id"],
                name=product_version.field_dict["description"],
                quantity=1,
                sku=f"{product_version.field_dict['content_type_id']}-{product_version.field_dict['object_id']}",
                unitprice=line_item_price,
                taxable=0,
            )
        )

    order.total_price_paid = total
    order.save()

    basket.delete()

    if features.is_enabled(features.CHECKOUT_TEST_UI):
        response_uri = reverse("checkout_test_decode_response")
    else:
        response_uri = reverse("checkout-decode_response")

    payload = PaymentGateway.start_payment(
        ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,
        gateway_order,
        request.build_absolute_uri(response_uri),
        request.build_absolute_uri(response_uri),
    )

    return payload


class CheckoutApiViewSet(ViewSet):
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    @action(
        detail=False,
        methods=["post"],
        name="Redeem Discount",
        url_name="redeem_discount",
    )
    def redeem_discount(self, request):
        """
        API call to redeem a discount. Discounts are attached to the basket so
        they can be attached at any time in the checkout process. Later on,
        they'll be converted to attach to the resulting Order (as Baskets are
        ephemeral).

        POST Args:
            - discount (int): Discount ID to apply

        Returns:
            - Success message on success
            - HTTP 406 if there's no basket yet
            - HTTP 404 if the discount isn't found
        """
        try:
            basket = Basket.objects.filter(user=request.user).get()
        except ObjectDoesNotExist:
            return Response("No basket", status=status.HTTP_406_NOT_ACCEPTABLE)

        try:
            discount = Discount.objects.get(pk=request.data["discount"])
        except ObjectDoesNotExist:
            return Response("Discount not found.", status=status.HTTP_404_NOT_FOUND)

        basket_discount = BasketDiscount(
            redemption_date=now_in_utc(),
            redeemed_by=request.user,
            redeemed_discount=discount,
            redeemed_basket=basket,
        )
        basket_discount.save()

        # This should maybe recalculate the pricing for stuff in the basket?

        return Response({"message": "Discount applied", "id": basket_discount.id})

    @action(
        detail=False, methods=["post"], name="Start Checkout", url_name="start_checkout"
    )
    def start_checkout(self, request):
        """
        API call to start the checkout process. This assembles the basket items
        into an Order with Lines for each item, applies the attached basket
        discounts, and then calls the payment gateway to prepare for payment.

        Returns:
            - JSON payload from the ol-django payment gateway app. The payment
              gateway returns data necessary to construct a form that will
              ultimately POST to the actual payment processor.
        """
        try:
            payload = generate_checkout_payload(request)
        except ObjectDoesNotExist:
            return Response("No basket", status=status.HTTP_406_NOT_ACCEPTABLE)

        return Response(payload)

    @action(detail=False, methods=["get"], name="Cart Info", url_name="cart")
    def cart(self, request):
        """
        Returns the current cart, with the product info embedded.
        """
        try:
            basket = Basket.objects.filter(user=request.user).get()
        except ObjectDoesNotExist:
            return Response("No basket", status=status.HTTP_406_NOT_ACCEPTABLE)

        return Response(BasketWithProductSerializer(basket).data)


class IsSignedByPaymentGateway(BasePermission):
    """
    Verifies the payload that comes back from the payment processor is properly
    signed. Defaulting to CyberSource for now but this should make its way into
    ol-django.
    """

    def has_permission(self, request, view):
        # this line for when the ol-django stuff comes through
        #         return PaymentGateway.validate_processor_response(ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request)

        if request.method == "GET":
            passed_payload = request.query_params
        else:
            passed_payload = request.data

        cybersource = CyberSourcePaymentGateway()

        signature = cybersource._generate_cybersource_sa_signature(passed_payload)

        if passed_payload["signature"] == signature:
            return True
        else:
            return False


class CheckoutViewSet(ViewSet):
    """
    The methods here are stubs for now. These should handle the responses from
    CyberSource or other payment gateway so they can handle the result of the
    transaction, and then redirect into the CMS or something appropriate when
    they're done. That stuff doesn't exist yet so these will return a JSON blob
    instead for now.
    """

    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsSignedByPaymentGateway,)

    def __init__(self, *args, **kwargs):
        import logging

        self.logger = logging.getLogger(__name__)

    @action(
        detail=False,
        methods=["get"],
        name="Cancel Checkout",
        url_name="cancel_checkout",
    )
    def cancel_checkout(self, request):
        """
        If the user cancels out of the transaction while on the payment
        processor's site, they will be redirected here. This should then clear
        out pending orders and (probably) send the customer somewhere where
        they can start over.
        """
        orders = Order.objects.filter(
            purchaser=request.user, state=Order.STATE.PENDING
        ).all()

        for order in orders:
            order.state = Order.STATE.CANCELED
            order.save()

        return Response({"message": "Order cancelled"})

    @action(
        detail=False, methods=["get", "post"], name="Receipt View", url_name="receipt"
    )
    def receipt(self, request):
        """
        This is where customers should land when they have completed the
        transaction successfully. This does a handful of things:
        1. Verifies the incoming payload, which should be signed by the
        processor
        2. Finds and fulfills the order in the system (which should also then
        clear out the stored basket)
        3. Perform any enrollments, account status changes, etc.
        """
        orders = PendingOrder.objects.filter(purchaser=request.user).all()

        for order in orders:
            order.state = Order.STATE.FULFILLED
            order.save()

        return Response(OrderSerializer(orders, many=True).data)

    @action(
        detail=False,
        methods=["get", "post"],
        name="Processor Response",
        url_name="decode_response",
    )
    def decode_response(self, request):
        """
        Processes the response from the payment processor and performs an
        appropriate action. This may be either a success, in which case something
        good should happen, or a failure, in which case fall over screaming.
        """

        processor_response = PaymentGateway.get_formatted_response(
            ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
        )
        converted_order = PaymentGateway.get_gateway_class(
            ECOMMERCE_DEFAULT_PAYMENT_GATEWAY
        ).convert_to_order(processor_response)

        order = Order.objects.get(pk=converted_order.reference, purchaser=request.user)

        if processor_response.state == ProcessorResponse.STATE_DECLINED:
            # Transaction declined for some reason
            # This probably means the order needed to go through the process
            # again so maybe tell the user to do a thing.
            self.logger.debug(
                "Transaction declined: {msg}".format(msg=processor_response["message"])
            )
        elif processor_response.state == ProcessorResponse.STATE_ERROR:
            # Error - something went wrong with the request
            self.logger.debug(
                "Error happened submitting the transaction: {msg}".format(
                    msg=processor_response["message"]
                )
            )
        elif processor_response.state == ProcessorResponse.STATE_CANCELLED:
            # Transaction cancelled
            # Transaction could be cancelled for reasons that don't necessarily
            # mean that the entire order is invalid, so we'll do nothing with
            # the order here.
            self.logger.debug(
                "Transaction cancelled: {msg}".format(msg=processor_response["message"])
            )
        elif processor_response.state == ProcessorResponse.STATE_REVIEW:
            # Transaction held for review in the payment processor's system
            # The transaction is in limbo here - it may be approved or denied
            # at a later time
            self.logger.debug(
                "Transaction flagged for review: {msg}".format(
                    msg=processor_response["message"]
                )
            )
        elif processor_response.state == ProcessorResponse.STATE_ACCEPTED:
            # It actually worked here
            self.logger.debug(
                "Transaction accepted!: {msg}".format(msg=processor_response["message"])
            )

            order.state = Order.STATE.FULFILLED
            order.save()

        return Response({})


class CheckoutInterstitialView(LoginRequiredMixin, TemplateView):
    template_name = "checkout_interstitial.html"

    def get(self, request):
        try:
            checkout_payload = generate_checkout_payload(request)
        except ObjectDoesNotExist:
            return HttpResponse("No basket")

        return render(
            request,
            self.template_name,
            {"checkout_payload": checkout_payload, "form": checkout_payload["payload"]},
        )


@method_decorator(csrf_exempt, name="dispatch")
class CheckoutDecodeResponseView(TemplateView):
    def __init__(self, *args, **kwargs):
        import logging

        self.logger = logging.getLogger(__name__)

    def post(self, request):
        """
        Processes the response from the payment processor and performs an
        appropriate action. This determines what the status of the request
        ended up being, and then displays the appropriate resposne page.

        At the moment, this code does not do the following:
        - Any enrollments or user changes once a transaction has completed
        successfully. (It does change the state of the order once it's accepted
        but there's more steps to the process.)
        - Display any of the actual UI code. There are some stub templates in
        here for testing purposes. Once the UI is ready, this code should be
        amended to redirect to the proper location or display the actual UI once
        it has finished processing the transaction.
        """
        if not PaymentGateway.validate_processor_response(
            ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
        ):
            raise PermissionDenied(
                "Could not validate response from the payment processor."
            )

        fmt_response = PaymentGateway.get_formatted_response(
            ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
        )

        order_id = Order.decode_reference_number(request.POST["req_reference_number"])

        order = Order.objects.get(pk=order_id)

        template = "test_checkout_successful.html"

        if fmt_response.state == ProcessorResponse.STATE_DECLINED:
            # Transaction declined for some reason
            # This probably means the order needed to go through the process
            # again so maybe tell the user to do a thing.
            self.logger.debug(
                "Transaction declined: {msg}".format(msg=fmt_response.message)
            )
            template = "test_checkout_declined.html"
        elif fmt_response.state == ProcessorResponse.STATE_ERROR:
            # Error - something went wrong with the request
            self.logger.debug(
                "Error happened submitting the transaction: {msg}".format(
                    msg=fmt_response.message
                )
            )
            template = "test_checkout_error.html"
        elif fmt_response.state == ProcessorResponse.STATE_CANCELLED:
            # Transaction cancelled
            # Transaction could be cancelled for reasons that don't necessarily
            # mean that the entire order is invalid, so we'll do nothing with
            # the order here.
            self.logger.debug(
                "Transaction cancelled: {msg}".format(msg=fmt_response.message)
            )

            template = "test_checkout_cancelled.html"
        elif fmt_response.state == ProcessorResponse.STATE_REVIEW:
            # Transaction needs a professional review
            # (nonjokey - someone needs to approve this so the order shouldn't be cancelled quite yet)
            self.logger.debug(
                "Transaction flagged for review: {msg}".format(msg=fmt_response.message)
            )

            template = "test_chekcout_review.html"
        elif fmt_response.state == ProcessorResponse.STATE_ACCEPTED:
            # It actually worked here
            self.logger.debug(
                "Transaction accepted!: {msg}".format(msg=fmt_response.message)
            )

            order.state = Order.STATE.FULFILLED
            order.save()

            template = "test_checkout_accept.html"

        return render(
            request,
            template,
            {
                "order": order,
                "fmt_response": fmt_response,
                "full_response": request.POST,
            },
        )


"""
These are testing stubs - they will allow you to fairly easily run a transaction
through the whole workflow. These should be replaced with the actual workflow
when that's more ready to go. (They should be removed when there's real UI.)
"""


class CheckoutTestView(TemplateView):
    template_name = "test_checkout_post.html"

    def get(self, request):
        """
        Generates a basket, and then adds a program to it, then gives you a form
        so you can check out through the payment processor.
        """
        import random

        if not request.user.is_superuser:
            raise PermissionDenied("Not an admin user.")

        if Product.objects.count() == 0:
            raise Exception("You need to set up a product first.")

        if Basket.objects.filter(user=request.user).count() == 0:
            basket = Basket(user=request.user)
            basket.save()
        else:
            basket = Basket.objects.filter(user=request.user).get()

        if basket.basket_items.count() == 0:
            products = Product.objects.all()

            basket_item = BasketItem(
                product=products[random.randrange(0, len(products), 1)],
                basket=basket,
                quantity=1,
            )
            basket_item.save()

        return render(
            request,
            self.template_name,
            {
                "step2": reverse("checkout_test_step2"),
                "int_checkout_url": reverse("checkout_api-start_checkout"),
            },
        )


class CheckoutTestStepTwoView(TemplateView):
    template_name = "test_checkout_post_step2.html"

    def post(self, request):
        """
        Grabs the generated payload and then generates a form for you to actually
        submit to the payment processor. Maybe this can be one step.
        """
        if not request.user.is_superuser:
            raise PermissionDenied("Not an admin user.")

        import json

        payload = json.loads(request.POST["checkout_payload"])

        return render(
            request,
            self.template_name,
            {"checkout_payload": payload, "form": payload["payload"]},
        )
