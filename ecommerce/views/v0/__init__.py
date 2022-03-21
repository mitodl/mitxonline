"""
MITxOnline ecommerce views
"""
import logging
from main.constants import (
    USER_MSG_TYPE_PAYMENT_ACCEPTED,
    USER_MSG_TYPE_PAYMENT_CANCELLED,
    USER_MSG_TYPE_PAYMENT_DECLINED,
    USER_MSG_TYPE_PAYMENT_ERROR,
    USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN,
    USER_MSG_TYPE_PAYMENT_REVIEW,
)
from main.utils import redirect_with_user_message
from rest_framework import mixins, status
from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView
from rest_framework.viewsets import ReadOnlyModelViewSet, GenericViewSet, ViewSet
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from django.views.generic import TemplateView, RedirectView, View
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied

from django.urls import reverse
from main.settings import ECOMMERCE_DEFAULT_PAYMENT_GATEWAY

from mitol.common.utils import now_in_utc
from rest_framework_extensions.mixins import NestedViewSetMixin
from mitol.payment_gateway.api import (
    PaymentGateway,
    ProcessorResponse,
)

from courses.models import (
    CourseRun,
    Course,
    Program,
    ProgramRun,
)

from ecommerce import api
from ecommerce.serializers import (
    OrderHistorySerializer,
    ProductSerializer,
    BasketSerializer,
    BasketItemSerializer,
    BasketDiscountSerializer,
    BasketWithProductSerializer,
    OrderSerializer,
)
from ecommerce.models import (
    Product,
    Basket,
    BasketItem,
    Discount,
    BasketDiscount,
    UserDiscount,
    PendingOrder,
    FulfilledOrder,
    Order,
)
from ecommerce.forms import AdminRefundOrderForm

log = logging.getLogger(__name__)


class ProductsPagination(LimitOffsetPagination):
    default_limit = 2
    limit_query_param = "l"
    offset_query_param = "o"
    max_limit = 50


class OrderHistoryPagination(LimitOffsetPagination):
    default_limit = 10
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


class BasketDiscountViewSet(ReadOnlyModelViewSet):
    """Applied basket discounts"""

    serializer_class = BasketDiscountSerializer

    def get_queryset(self):
        return BasketDiscount.objects.filter(redeemed_basket__user=self.request.user)


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
            - discount (str): Discount Code to apply

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
            discount = Discount.objects.get(discount_code=request.data["discount"])
            if not discount.check_validity(request.user):
                raise ObjectDoesNotExist()
        except ObjectDoesNotExist:
            return Response(
                f"Discount '{request.data['discount']}' not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        # If you try to redeem a second code, clear out the discounts that
        # have been redeemed.
        BasketDiscount.objects.filter(redeemed_basket=basket).delete()

        basket_discount = BasketDiscount(
            redemption_date=now_in_utc(),
            redeemed_by=request.user,
            redeemed_discount=discount,
            redeemed_basket=basket,
        )
        basket_discount.save()

        return Response(
            {
                "message": "Discount applied",
                "code": basket_discount.redeemed_discount.discount_code,
            }
        )

    @action(
        detail=False,
        methods=["post"],
        name="Clear Discount",
        url_name="clear_discount",
    )
    def clear_discount(self, request):
        """
        API call to clear discounts from the current cart. This will reapply
        UserDiscounts.

        Returns:
            - Success message on success
        """
        basket = Basket.objects.filter(user=request.user).get_or_create()

        if basket[1]:
            basket[0].save()

        BasketDiscount.objects.filter(redeemed_basket=basket[0]).delete()

        api.apply_user_discounts(request.user)

        return Response("Discounts cleared")

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
            payload = api.generate_checkout_payload(request)
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

        # don't auto-apply user discounts if they've added their own code
        # this may need to be revisited
        if BasketDiscount.objects.filter(redeemed_basket=basket).count() == 0:
            api.apply_user_discounts(request.user)

        return Response(BasketWithProductSerializer(basket).data)


@method_decorator(csrf_exempt, name="dispatch")
class CheckoutCallbackView(View):
    """
    Handle a checkout cancellation or receipt
    """

    def __init__(self, *args, **kwargs):
        import logging

        self.logger = logging.getLogger(__name__)

    def post(self, request, *args, **kwargs):
        """
        This is where customers should land when they have completed the
        transaction successfully. This does a handful of things:
        1. Verifies the incoming payload, which should be signed by the
        processor
        2. Finds and fulfills the order in the system (which should also then
        clear out the stored basket)
        3. Perform any enrollments, account status changes, etc.
        """
        if not PaymentGateway.validate_processor_response(
            ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
        ):
            raise PermissionDenied(
                "Could not validate response from the payment processor."
            )

        payment_data = request.POST

        processor_response = PaymentGateway.get_formatted_response(
            ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
        )
        converted_order = PaymentGateway.get_gateway_class(
            ECOMMERCE_DEFAULT_PAYMENT_GATEWAY
        ).convert_to_order(payment_data)

        order_id = Order.decode_reference_number(converted_order.reference)

        try:
            order = Order.objects.get(pk=order_id)
        except ObjectDoesNotExist:
            return HttpResponse("Order not found")

        basket = Basket.objects.filter(user=order.purchaser).first()

        if processor_response.state == ProcessorResponse.STATE_DECLINED:
            # Transaction declined for some reason
            # This probably means the order needed to go through the process
            # again so maybe tell the user to do a thing.
            self.logger.debug(
                "Transaction declined: {msg}".format(msg=processor_response.message)
            )
            order.decline()
            order.save()
            return redirect_with_user_message(
                reverse("cart"), {"type": USER_MSG_TYPE_PAYMENT_DECLINED}
            )
        elif processor_response.state == ProcessorResponse.STATE_ERROR:
            # Error - something went wrong with the request
            self.logger.debug(
                "Error happened submitting the transaction: {msg}".format(
                    msg=processor_response.message
                )
            )
            order.error()
            order.save()
            return redirect_with_user_message(
                reverse("cart"), {"type": USER_MSG_TYPE_PAYMENT_ERROR}
            )
        elif processor_response.state == ProcessorResponse.STATE_CANCELLED:
            # Transaction cancelled
            # Transaction could be cancelled for reasons that don't necessarily
            # mean that the entire order is invalid, so we'll do nothing with
            # the order here (other than set it to Cancelled)
            self.logger.debug(
                "Transaction cancelled: {msg}".format(msg=processor_response.message)
            )
            order.cancel()
            order.save()
            return redirect_with_user_message(
                reverse("cart"), {"type": USER_MSG_TYPE_PAYMENT_CANCELLED}
            )
        elif processor_response.state == ProcessorResponse.STATE_REVIEW:
            # Transaction held for review in the payment processor's system
            # The transaction is in limbo here - it may be approved or denied
            # at a later time
            self.logger.debug(
                "Transaction flagged for review: {msg}".format(
                    msg=processor_response.message
                )
            )
            if basket:
                basket.delete()

            return redirect_with_user_message(
                reverse("user-dashboard"), {"type": USER_MSG_TYPE_PAYMENT_REVIEW}
            )
        elif processor_response.state == ProcessorResponse.STATE_ACCEPTED:
            # It actually worked here
            self.logger.debug(
                "Transaction accepted!: {msg}".format(msg=processor_response.message)
            )

            return api.fulfill_completed_order(order, payment_data, basket)
        else:
            order.cancel()
            order.save()
            return redirect_with_user_message(
                reverse("user-dashboard"), {"type": USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN}
            )


class CheckoutProductView(LoginRequiredMixin, RedirectView):
    """View to add products to the cart and proceed to the checkout page"""

    pattern_name = "cart"

    def get_redirect_url(self, *args, **kwargs):
        """Populate the basket before redirecting"""
        with transaction.atomic():
            basket, _ = Basket.objects.select_for_update().get_or_create(
                user=self.request.user
            )
            basket.basket_items.all().delete()

            for product in Product.objects.filter(
                id__in=self.request.GET.getlist("product_id")
            ):
                BasketItem.objects.create(basket=basket, product=product)

        return super().get_redirect_url(*args, **kwargs)


class CheckoutInterstitialView(LoginRequiredMixin, TemplateView):
    template_name = "checkout_interstitial.html"

    def get(self, request):
        try:
            checkout_payload = api.generate_checkout_payload(request)
        except ObjectDoesNotExist:
            return HttpResponse("No basket")

        if "no_checkout" in checkout_payload:
            return checkout_payload["response"]

        return render(
            request,
            self.template_name,
            {"checkout_payload": checkout_payload, "form": checkout_payload["payload"]},
        )


class OrderHistoryViewSet(ReadOnlyModelViewSet):
    serializer_class = OrderHistorySerializer
    pagination_class = OrderHistoryPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(purchaser=self.request.user).all()


class OrderReceiptView(RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(purchaser=self.request.user).all()


class AdminRefundOrderView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "refund_order_confirm.html"
    permission_required = "is_superuser"

    def post(self, request):
        try:
            refund_form = AdminRefundOrderForm(request.POST)
            order = FulfilledOrder.objects.get(pk=request.POST["order"])

            if refund_form.is_valid():
                unenrolled = order.refund(
                    request.POST["refund_amount"],
                    request.POST["refund_reason"],
                    True
                    if "perform_unenrolls" in request.POST
                    and request.POST["perform_unenrolls"]
                    else False,
                )
                order.save()

                if unenrolled:
                    messages.success(
                        request, f"Order {order.reference_number} refunded."
                    )
                else:
                    messages.warning(
                        request,
                        f"Order {order.reference_number} refunded, but could not unenroll the learner. Unenrollments will be reattempted later.",
                    )

                return HttpResponseRedirect(
                    reverse("admin:ecommerce_refundedorder_change", args=(order.id,))
                )

            errors = []
            error_messages = {}

            for whatever in refund_form.errors:
                errors.append(whatever)
                error_messages[whatever] = refund_form.errors[whatever]

            return render(
                request,
                self.template_name,
                {
                    "refund_form": refund_form,
                    "order": order,
                    "form_valid": refund_form.is_valid(),
                    "errors": errors,
                    "error_messages": error_messages,
                },
            )
        except NotImplementedError:
            messages.error(request, f"Order {request.POST['order']} can't be refunded.")
            return HttpResponseRedirect(
                reverse("admin:ecommerce_refundedorder_changelist")
            )
        except ObjectDoesNotExist:
            messages.error(
                request,
                f"Order {request.POST['order']} could not be found - is it Fulfilled?",
            )
            return HttpResponseRedirect(
                reverse("admin:ecommerce_fulfilledorder_changelist")
            )

    def get(self, request):
        try:
            order = FulfilledOrder.objects.get(pk=request.GET["order"])

            if order.state != Order.STATE.FULFILLED:
                raise ObjectDoesNotExist()
        except ObjectDoesNotExist:
            messages.error(
                request,
                f"Order {request.GET['order']} could not be found - is it Fulfilled?",
            )
            return HttpResponseRedirect(
                reverse("admin:ecommerce_fulfilledorder_changelist")
            )

        refund_form = AdminRefundOrderForm(
            initial={
                "_selected_action": order.id,
                "refund_amount": order.total_price_paid,
            }
        )

        return render(
            request,
            self.template_name,
            {
                "refund_form": refund_form,
                "order": order,
                "form_valid": True,
                "errors": {},
            },
        )
