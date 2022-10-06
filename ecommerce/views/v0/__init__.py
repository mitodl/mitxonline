"""
MITxOnline ecommerce views
"""
import logging
from main.utils import redirect_with_user_message
from main.settings import ECOMMERCE_DEFAULT_PAYMENT_GATEWAY
from rest_framework import mixins, status
from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView
from rest_framework.viewsets import (
    ReadOnlyModelViewSet,
    GenericViewSet,
    ViewSet,
    ModelViewSet,
)
from rest_framework.views import APIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action

from main.constants import (
    USER_MSG_TYPE_PAYMENT_ACCEPTED,
    USER_MSG_TYPE_PAYMENT_CANCELLED,
    USER_MSG_TYPE_PAYMENT_DECLINED,
    USER_MSG_TYPE_PAYMENT_ERROR,
    USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN,
    USER_MSG_TYPE_PAYMENT_REVIEW,
    USER_MSG_TYPE_ENROLL_BLOCKED,
)

from django.views.generic import TemplateView, RedirectView, View
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, Count
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.urls import reverse

from mitol.common.utils import now_in_utc
from rest_framework_extensions.mixins import NestedViewSetMixin
from mitol.payment_gateway.api import PaymentGateway

from courses.models import (
    CourseRun,
    Course,
    Program,
    ProgramRun,
)

from ecommerce import api
from ecommerce.discounts import DiscountType
from ecommerce.serializers import (
    OrderHistorySerializer,
    ProductSerializer,
    BasketSerializer,
    BasketItemSerializer,
    BasketDiscountSerializer,
    BasketWithProductSerializer,
    OrderSerializer,
    DiscountSerializer,
    DiscountRedemptionSerializer,
    DiscountProductSerializer,
    UserDiscountSerializer,
    UserDiscountMetaSerializer,
)
from ecommerce.models import (
    Product,
    Basket,
    BasketItem,
    Discount,
    DiscountRedemption,
    DiscountProduct,
    BasketDiscount,
    UserDiscount,
    Order,
)

from flexiblepricing.api import determine_courseware_flexible_price_discount

log = logging.getLogger(__name__)


class ECommerceDefaultPagination(LimitOffsetPagination):
    default_limit = 10
    limit_query_param = "l"
    offset_query_param = "o"
    max_limit = 50


class ProductsPagination(ECommerceDefaultPagination):
    default_limit = 2


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


class DiscountViewSet(ModelViewSet):
    """API view set for Discounts"""

    serializer_class = DiscountSerializer
    queryset = Discount.objects.all()
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated, IsAdminUser)
    pagination_class = ECommerceDefaultPagination


class NestedDiscountProductViewSet(NestedViewSetMixin, ModelViewSet):
    """API view set for Discounts"""

    serializer_class = DiscountProductSerializer
    queryset = DiscountProduct.objects.all()
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated, IsAdminUser)
    pagination_class = ECommerceDefaultPagination


class NestedDiscountRedemptionViewSet(NestedViewSetMixin, ModelViewSet):
    """API view set for Discount Redemptions"""

    serializer_class = DiscountRedemptionSerializer
    queryset = DiscountRedemption.objects.all()
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated, IsAdminUser)
    pagination_class = ECommerceDefaultPagination


class NestedUserDiscountViewSet(NestedViewSetMixin, ModelViewSet):
    """
    API view set for User Discounts. This one is for use within a Discount.
    """

    serializer_class = UserDiscountMetaSerializer
    queryset = UserDiscount.objects.all()
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated, IsAdminUser)
    pagination_class = ECommerceDefaultPagination


class UserDiscountViewSet(ModelViewSet):
    """API view set for User Discounts. This one is for working with the set as a whole."""

    serializer_class = UserDiscountSerializer
    queryset = UserDiscount.objects.all()
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated, IsAdminUser)
    pagination_class = ECommerceDefaultPagination


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

        Discount application is subject to these rules:
        - The discount can't be flagged for use with flexible pricing.
        - If the discount is tied to a product, the product must already be in
          the basket.

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
            discount = Discount.objects.filter(for_flexible_pricing=False).get(
                discount_code=request.data["discount"]
            )

            if not api.check_discount_for_products(discount, basket):
                raise ObjectDoesNotExist()

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

        product = BasketItem.objects.get(basket=basket).product
        flexible_price_discount = determine_courseware_flexible_price_discount(
            product, request.user
        )
        if flexible_price_discount:
            flexible_price = DiscountType.get_discounted_price(
                [flexible_price_discount], product
            )
            discounted_price = DiscountType.get_discounted_price([discount], product)
            if flexible_price < discounted_price:
                discount = flexible_price_discount

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

        if not basket.get_products():
            return Response(
                "No product in basket", status=status.HTTP_406_NOT_ACCEPTABLE
            )

        api.apply_user_discounts(request)

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

        with transaction.atomic():
            order = api.get_order_from_cybersource_payment_response(request)
            if order is None:
                return HttpResponse("Order not found")
            # We only want to process responses related to orders which are PENDING
            # otherwise we can conclude that we already received a response through
            # BackofficeCallbackView.
            order_state = None
            if order.state == Order.STATE.PENDING:
                order_state = api.process_cybersource_payment_response(request, order)

            if order_state == Order.STATE.CANCELED:
                return redirect_with_user_message(
                    reverse("cart"), {"type": USER_MSG_TYPE_PAYMENT_CANCELLED}
                )
            elif order_state == Order.STATE.ERRORED:
                return redirect_with_user_message(
                    reverse("cart"), {"type": USER_MSG_TYPE_PAYMENT_ERROR}
                )
            elif order_state == Order.STATE.DECLINED:
                return redirect_with_user_message(
                    reverse("cart"), {"type": USER_MSG_TYPE_PAYMENT_DECLINED}
                )
            elif order_state == Order.STATE.REVIEW:
                basket = Basket.objects.filter(user=order.purchaser).first()
                if basket:
                    if basket.has_user_blocked_products(order.purchaser):
                        return redirect_with_user_message(
                            reverse("user-dashboard"),
                            {"type": USER_MSG_TYPE_ENROLL_BLOCKED},
                        )
                    else:
                        return redirect_with_user_message(
                            reverse("user-dashboard"),
                            {"type": USER_MSG_TYPE_PAYMENT_REVIEW},
                        )
            elif order_state == Order.STATE.FULFILLED:
                return redirect_with_user_message(
                    reverse("user-dashboard"),
                    {
                        "type": USER_MSG_TYPE_PAYMENT_ACCEPTED,
                        "run": order.lines.first().purchased_object.course.title,
                    },
                )
            else:
                if not PaymentGateway.validate_processor_response(
                    ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
                ):
                    log.info("Could not validate payment response for order")
                else:
                    processor_response = PaymentGateway.get_formatted_response(
                        ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
                    )
                log.info(
                    "Checkout callback unknown error for transaction_id %s, state %s, reason_code %s, message %s, and ProcessorResponse %s",
                    processor_response.transaction_id,
                    order.state,
                    processor_response.response_code,
                    processor_response.message,
                    processor_response,
                )
                return redirect_with_user_message(
                    reverse("user-dashboard"),
                    {"type": USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN},
                )


@method_decorator(csrf_exempt, name="dispatch")
class BackofficeCallbackView(APIView):
    authentication_classes = []  # disables authentication
    permission_classes = []  # disables permission

    def post(self, request, *args, **kwargs):
        """
        This endpoint is called by Cybersource as a server-to-server call
        in order to respond with the payment details.

        Returns:
            - HTTP_200_OK if the Order is found.

        Raises:
            - Http404 if the Order is not found.
        """
        with transaction.atomic():
            order = api.get_order_from_cybersource_payment_response(request)

            # We only want to process responses related to orders which are PENDING
            # otherwise we can conclude that we already received a response through
            # the user's browser.
            if order is None:
                raise Http404
            elif order.state == Order.STATE.PENDING:
                api.process_cybersource_payment_response(request, order)

            return Response(status=status.HTTP_200_OK)


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
            BasketDiscount.objects.filter(redeemed_basket=basket).delete()

            # Incoming product ids from internal checkout
            all_product_ids = self.request.GET.getlist("product_id")

            # If the request is from an external source we would have course_id as query param
            # Note that course_id passed in param corresponds to course run's courseware_id on mitxonline
            course_run_ids = self.request.GET.getlist("course_run_id")
            course_ids = self.request.GET.getlist("course_id")
            program_ids = self.request.GET.getlist("program_id")

            all_product_ids.extend(
                list(
                    CourseRun.objects.filter(
                        Q(courseware_id__in=course_run_ids)
                        | Q(courseware_id__in=course_ids)
                    ).values_list("products__id", flat=True)
                )
            )
            all_product_ids.extend(
                list(
                    ProgramRun.objects.filter(program__id__in=program_ids).values_list(
                        "products__id", flat=True
                    )
                )
            )
            for product in Product.objects.filter(id__in=all_product_ids):
                BasketItem.objects.create(basket=basket, product=product)

        return super().get_redirect_url(*args, **kwargs)


class CheckoutInterstitialView(LoginRequiredMixin, TemplateView):
    template_name = "checkout_interstitial.html"

    def get(self, request):
        try:
            checkout_payload = api.generate_checkout_payload(request)
        except ObjectDoesNotExist:
            return HttpResponse("No basket")
        if "country_blocked" in checkout_payload:
            return checkout_payload["response"]
        if "no_checkout" in checkout_payload:
            return checkout_payload["response"]
        if "purchased_same_courserun" in checkout_payload:
            return checkout_payload["response"]
        if "purchased_non_upgradeable_courserun" in checkout_payload:
            return checkout_payload["response"]
        if "invalid_discounts" in checkout_payload:
            return checkout_payload["response"]

        return render(
            request,
            self.template_name,
            {"checkout_payload": checkout_payload, "form": checkout_payload["payload"]},
        )


class OrderHistoryViewSet(ReadOnlyModelViewSet):
    serializer_class = OrderHistorySerializer
    pagination_class = ECommerceDefaultPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects.filter(purchaser=self.request.user)
            .filter(state__in=[Order.STATE.FULFILLED, Order.STATE.REFUNDED])
            .order_by("-created_on")
            .all()
        )


class OrderReceiptView(RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(purchaser=self.request.user).all()
