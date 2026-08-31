"""
MITx Online API-ready views, migrated from Unified Ecommerce.
"""

import logging

import django_filters
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect
from django.views import View
from django_filters import rest_framework as filters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from mitol.common.utils import now_in_utc
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ParseError
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework_extensions.mixins import NestedViewSetMixin

from b2b.api import is_product_courserun, is_product_program
from courses.models import (
    Course,
    CourseRun,
    PaidCourseRun,
    PaidProgram,
    Program,
    ProgramRun,
)
from courses.utils import is_uai_course_run, is_uai_program
from ecommerce.api import (
    apply_discount_to_basket,
    establish_basket,
    establish_basket_for_request,
    generate_checkout_payload,
    generate_discount_code,
    get_auto_apply_discounts_for_basket,
)
from ecommerce.exceptions import ProductBlockedError
from ecommerce.models import (
    Basket,
    BasketDiscount,
    BasketItem,
    Discount,
    DiscountProduct,
    DiscountRedemption,
    Order,
    OrderStatus,
    Product,
    UserDiscount,
)
from ecommerce.serializers import BulkDiscountSerializer
from ecommerce.serializers.v0 import (
    BasketItemSerializer,
    BasketWithProductSerializer,
    CheckoutPayloadSerializer,
    DiscountProductSerializer,
    DiscountRedemptionSerializer,
    OrderHistorySerializer,
    OrderSerializer,
    OrderStatusSerializer,
    ProductFlexiblePriceSerializer,
    ProductSerializer,
    RefundRequestSerializer,
    UserDiscountMetaSerializer,
    UserDiscountSerializer,
    V0DiscountSerializer,
    requests,
)
from ecommerce.tasks import send_refund_request_notification_email
from ecommerce.views.utils import AttachDiscountProductMixin
from flexiblepricing.models import FlexiblePriceTier
from flexiblepricing.serializers import FlexiblePriceTierSerializer
from hubspot_sync.task_helpers import sync_hubspot_cart_add

log = logging.getLogger(__name__)
User = get_user_model()


@extend_schema(
    description="Returns the basket items for the current user.",
    request=None,
    responses=BasketItemSerializer,
    parameters=[
        OpenApiParameter(
            name="parent_lookup_basket",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the parent basket",
            required=True,
        ),
        OpenApiParameter(
            name="id",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the basket item",
            required=True,
        ),
    ],
)
class BasketItemViewSet(ModelViewSet):
    """ViewSet for handling BasketItem operations."""

    permission_classes = (IsAuthenticated,)
    serializer_class = BasketItemSerializer

    def get_queryset(self):
        """Return only basket items owned by this user."""
        if getattr(self, "swagger_fake_view", False):
            return BasketItem.objects.none()

        return BasketItem.objects.filter(basket__user=self.request.user)


@extend_schema_view(
    list=extend_schema(
        description=("Retrives the current user's baskets."),
        parameters=[],
    ),
    retrieve=extend_schema(
        description="Retrieve a basket for the current user.",
        parameters=[
            OpenApiParameter("id", OpenApiTypes.INT, OpenApiParameter.PATH),
        ],
    ),
)
class BasketViewSet(ReadOnlyModelViewSet):
    """API view set for Basket"""

    serializer_class = BasketWithProductSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = (filters.DjangoFilterBackend,)

    def get_queryset(self):
        """Return only baskets owned by this user."""

        if getattr(self, "swagger_fake_view", False):
            return Basket.objects.none()

        return Basket.objects.filter(user=self.request.user).all()


@extend_schema(
    description=(
        "Creates or updates a basket for the current user, "
        "adding the discount if valid."
    ),
    methods=["POST"],
    request=None,
    responses=BasketWithProductSerializer,
    parameters=[
        OpenApiParameter(
            "discount_code", OpenApiTypes.STR, OpenApiParameter.QUERY, required=True
        ),
    ],
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def add_discount_to_basket(request):
    """
    Add a discount to the basket for the currently logged in user.

    POST Args:
        discount_code (str): discount code to apply to the basket

    Returns:
        Response: HTTP response
    """
    basket = Basket.establish_basket(request)
    discount_code = request.query_params.get("discount_code")

    try:
        discount = Discount.objects.get(discount_code=discount_code)
    except Discount.DoesNotExist:
        return Response(
            {"error": f"Discount '{discount_code}' not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        apply_discount_to_basket(basket, discount)
    except ValueError:
        return Response(
            {"error": "An error occurred while applying the discount."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        BasketWithProductSerializer(basket).data,
        status=status.HTTP_200_OK,
    )


def _create_basket_from_product(
    request, product_id: int, discount_code: str | None = None
):
    """
    Create a new basket item from a product for the currently logged in user. Reuse
    the existing basket object if it exists.

    If the checkout flag is set in the POST data, then this will create the
    basket, then immediately flip the user to the checkout interstitial (which
    then redirects to the payment gateway).

    If the discount code is provided, then it will be applied to the basket. If
    the discount isn't found or doesn't apply, then it will be ignored.

    Args:
        request (Request): The request object.
        product_id (int): Product ID
        discount_code (str): Discount code
    POST Args:
        quantity (int): quantity of the product to add to the basket (defaults to 1)
        checkout (bool): redirect to checkout interstitial (defaults to False)

    Returns:
        Response: HTTP response
    """
    quantity = request.data.get("quantity", 1)
    checkout = request.data.get("checkout", False)

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
        )

    with transaction.atomic():
        basket = establish_basket_for_request(request, for_update=True)

        # FUTURE: This is where the basket_add hook was called.

        (_, created) = BasketItem.objects.update_or_create(
            basket=basket, product=product, defaults={"quantity": quantity}
        )

        if request.user.is_authenticated:
            sync_hubspot_cart_add(
                request.user,
                product,
                is_uai=(
                    is_product_courserun(product)
                    and is_uai_course_run(product.purchasable_object)
                )
                or (
                    is_product_program(product)
                    and is_uai_program(product.purchasable_object)
                ),
            )

            # Discounts (including auto-applied financial assistance) are only
            # ever computed against a real user, and shouldn't show up at all for
            # a logged-out cart - so this whole step is skipped for anonymous
            # baskets rather than run against a basket with no user to check.
            existing_basket_discounts = [
                bd.redeemed_discount for bd in basket.discounts.all()
            ]
            discounts_to_apply = [
                *existing_basket_discounts,
                *list(get_auto_apply_discounts_for_basket(basket.id).all()),
            ]

            # Clear the discounts that are in the basket - we retained whatever was
            # already applied above and will re-apply so the codes get re-checked. (So,
            # if a code has now expired, you don't get it anymore.)
            BasketDiscount.objects.filter(redeemed_basket=basket).delete()

            for discount in discounts_to_apply:
                apply_discount_to_basket(basket, discount, allow_finaid=True)

            # Order matters - apply the code supplied last so we can always attach a
            # better-value discount by hand if we want. (Also, turn off finaid flag here.)
            if discount_code:
                try:
                    supplied_discount = Discount.objects.get(
                        discount_code=discount_code
                    )
                    apply_discount_to_basket(basket, supplied_discount)
                except Discount.DoesNotExist:
                    pass

    basket.refresh_from_db()

    if checkout:
        return redirect(
            "checkout_interstitial_page"
            if request.user.is_authenticated
            else "checkout-anonymous"
        )

    return Response(
        BasketWithProductSerializer(basket).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(
    description=(
        "Creates or updates a basket for the current user, adding the selected product."
    ),
    methods=["POST"],
    request=None,
    responses=BasketWithProductSerializer,
    parameters=[
        OpenApiParameter(
            "product_id", OpenApiTypes.INT, OpenApiParameter.PATH, required=True
        ),
    ],
)
@api_view(["POST"])
@permission_classes((AllowAny,))
def create_basket_from_product(request, product_id: int):
    """Run _create_basket_from_product."""

    return _create_basket_from_product(request, product_id)


@extend_schema(
    operation_id="create_basket_from_product_with_discount",
    description=(
        "Creates or updates a basket for the current user, "
        "adding the selected product and discount."
    ),
    methods=["POST"],
    request=None,
    responses=BasketWithProductSerializer,
    parameters=[
        OpenApiParameter(
            "product_id", OpenApiTypes.INT, OpenApiParameter.PATH, required=True
        ),
        OpenApiParameter(
            "discount_code", OpenApiTypes.STR, OpenApiParameter.PATH, required=True
        ),
    ],
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def create_basket_from_product_with_discount(
    request, product_id: int, discount_code: str | None = None
):
    """Run _create_basket_from_product with the discount code."""

    return _create_basket_from_product(request, product_id, discount_code)


@extend_schema(
    description=(
        "Creates or updates a basket for the current user, adding the selected product."
    ),
    methods=["POST"],
    responses=BasketWithProductSerializer,
    request=requests.CreateBasketWithProductsSerializer,
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def create_basket_with_products(request):
    """
    Create new basket items for the currently logged in user. Reuse the existing
    basket object if it exists. Optionally apply the supplied discount code.

    Eligible auto-apply and financial assistance discounts are applied whether
    or not a discount code is supplied.

    If the checkout flag is set in the POST data, then this will create the
    basket, then immediately flip the user to the checkout interstitial (which
    then redirects to the payment gateway).

    If any of the products aren't found, this will return a 404 error. A
    discount code that isn't found, isn't redeemable, or doesn't beat a
    discount already on the basket is dropped silently, and the basket is
    still updated.

    POST Args:
        product_ids (list[dict]): products to add to the basket, each
            ``{"product_id": int, "quantity": int}`` (required)
        checkout (bool): redirect to checkout interstitial (defaults to False)
        discount_code (str): discount code to apply to the basket (optional)

    Returns:
        Response: HTTP response
    """
    serializer = requests.CreateBasketWithProductsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    checkout = serializer.validated_data["checkout"]
    discount_code = serializer.validated_data["discount_code"]
    product_ids = serializer.validated_data["product_ids"]

    basket = establish_basket(request)
    products = []

    try:
        products = [
            (
                Product.objects.get(id=item["product_id"]),
                item["quantity"],
            )
            for item in product_ids
        ]
    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        for product, quantity in products:
            # FUTURE: this is where the basket_add hook is called
            BasketItem.objects.update_or_create(
                basket=basket, product=product, defaults={"quantity": quantity}
            )

            sync_hubspot_cart_add(
                request.user,
                product,
                is_uai=(
                    is_product_courserun(product)
                    and is_uai_course_run(product.purchasable_object)
                )
                or (
                    is_product_program(product)
                    and is_uai_program(product.purchasable_object)
                ),
            )
    except ProductBlockedError:
        return Response(
            {"error": "Product blocked from purchasing.", "product": product},
            status=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
        )

    auto_apply_discounts = get_auto_apply_discounts_for_basket(basket.id)
    for discount in auto_apply_discounts:
        apply_discount_to_basket(basket, discount, allow_finaid=True)

    if discount_code:
        try:
            discount = Discount.objects.get(discount_code=discount_code)
            apply_discount_to_basket(basket, discount)
        except Discount.DoesNotExist:
            pass

    basket.refresh_from_db()

    if checkout:
        return redirect("checkout_interstitial_page")

    return Response(
        BasketWithProductSerializer(basket).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    description="Clears the basket for the current user.",
    methods=["DELETE"],
    request=None,
    responses={204: OpenApiResponse(description="Basket cleared successfully")},
)
@api_view(["DELETE"])
@permission_classes([AllowAny])
def clear_basket(request):
    """
    Clear the basket for the current user.

    Returns:
        Response: HTTP response
    """
    with transaction.atomic():
        basket = establish_basket_for_request(request, for_update=True)
        basket.delete()

    return Response(None, status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    description=("Returns the payload necessary to start the payment process."),
    methods=["GET"],
    responses=CheckoutPayloadSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def checkout_basket(request):
    """
    Generate the data for checkout and return it.

    This gathers and converts the data in the current user's Basket, makes it
    into an Order, and returns the data to start the checkout process.
    """

    try:
        payload = generate_checkout_payload(request)
        req_status = (
            status.HTTP_400_BAD_REQUEST if "error" in payload else status.HTTP_200_OK
        )

        return Response(CheckoutPayloadSerializer(payload).data, status=req_status)
    except ObjectDoesNotExist:
        return Response("No basket", status=status.HTTP_400_BAD_REQUEST)


class ProductsPagination(LimitOffsetPagination):
    """Sets a default limit for the product list API."""

    default_limit = 2


class AllProductViewSet(ModelViewSet):
    """This doesn't filter unenrollable products out, and adds name search for
    courseware object readable id. It's really for the staff dashboard.
    """

    serializer_class = ProductSerializer
    pagination_class = ProductsPagination
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        """Get the queryset for products, including run and program information."""
        name_search = self.request.query_params.get("search")

        if name_search is None:
            return Product.objects.all()

        matching_courserun_ids = CourseRun.objects.filter(
            courseware_id__icontains=name_search
        ).values_list("id", flat=True)

        matching_program_ids = Program.objects.filter(
            readable_id__icontains=name_search
        ).values_list("id", flat=True)

        return (
            Product.objects.filter(
                (
                    Q(object_id__in=matching_courserun_ids)
                    & Q(content_type__model="courserun")
                )
                | (
                    Q(object_id__in=matching_program_ids)
                    & Q(content_type__model="program")
                )
                | (Q(description__icontains=name_search))
            )
            .select_related("content_type")
            .prefetch_related("purchasable_object")
        )


class ProductViewSet(ReadOnlyModelViewSet):
    """List and view products within the system."""

    serializer_class = ProductSerializer
    pagination_class = ProductsPagination

    def get_queryset(self):
        """Get product queryset, with course and program information."""

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
                | Q(all_requirements__course__in=unenrollable_course_ids)
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

    @extend_schema(
        operation_id="products_user_flexible_price_retrieve",
        description="Retrieve a product with user-specific flexible price information",
        responses={
            200: ProductFlexiblePriceSerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        permission_classes=[],
        url_path="user_flexible_price",
    )
    def user_flexible_price(self, request, **kwargs):  # noqa: ARG002
        """Get product with user-specific flexible price information."""
        product = self.get_object()
        serializer = ProductFlexiblePriceSerializer(
            product, context={"request": request}
        )
        return Response(serializer.data)


class DiscountFilterSet(django_filters.FilterSet):
    """Custom filtering for discounts."""

    q = django_filters.CharFilter(
        field_name="discount_code", label="q", lookup_expr="icontains"
    )
    is_redeemed = django_filters.ChoiceFilter(
        method="redeemed_filter", choices=(("yes", "yes"), ("no", "no"))
    )

    def redeemed_filter(self, qs, name, value):  # noqa: ARG002
        """Filter by discount redemption status."""

        qs = qs.annotate(num_redemptions=Count("order_redemptions"))

        if value == "yes":
            qs = qs.filter(num_redemptions__gt=0)
        elif value == "no":
            qs = qs.filter(num_redemptions=0)

        return qs

    class Meta:
        model = Discount
        fields = [
            "q",
            "redemption_type",
            "payment_type",
            "is_redeemed",
        ]


class DiscountViewSet(ModelViewSet):
    """API view set for Discounts"""

    queryset = Discount.objects.order_by("-created_on").all()
    serializer_class = V0DiscountSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser,)
    pagination_class = LimitOffsetPagination
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = DiscountFilterSet

    # filters=False and pagination_class=None because the schema otherwise
    # inherits the viewset's filter and pagination query params, which this
    # POST action never reads.
    @extend_schema(
        request=BulkDiscountSerializer,
        responses={201: V0DiscountSerializer(many=True)},
        filters=False,
    )
    @action(
        url_name="create_batch",
        detail=False,
        methods=["post"],
        pagination_class=None,
    )
    def create_batch(self, request):
        """
        Create a batch of codes. This is used in the staff-dashboard.
        POST arguments are the same as in generate_discount_code - look there
        for details.
        """
        otherSerializer = BulkDiscountSerializer(data=request.data)

        if otherSerializer.is_valid():
            generated_codes = generate_discount_code(**otherSerializer.validated_data)

            discounts = V0DiscountSerializer(generated_codes, many=True)

            return Response(discounts.data, status=status.HTTP_201_CREATED)

        raise ParseError(f"Batch creation failed: {otherSerializer.errors}")  # noqa: EM102


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="parent_lookup_discount",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the parent discount",
            required=True,
        ),
        OpenApiParameter(
            name="id",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the discount product",
            required=True,
        ),
    ]
)
class NestedDiscountProductViewSet(
    AttachDiscountProductMixin, NestedViewSetMixin, ModelViewSet
):
    """API view set for Discounts"""

    serializer_class = DiscountProductSerializer
    queryset = DiscountProduct.objects.all()
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser,)
    pagination_class = LimitOffsetPagination

    def destroy(self, request, **kwargs):  # noqa: ARG002
        """Delete a linked product from a discount."""

        discount = Discount.objects.get(pk=kwargs["parent_lookup_discount"])
        product = Product.objects.get(pk=kwargs["pk"])

        DiscountProduct.objects.filter(discount=discount, product=product).delete()

        return Response(
            DiscountProductSerializer(
                DiscountProduct.objects.filter(discount=discount).all(), many=True
            ).data
        )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="parent_lookup_redeemed_discount",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the parent discount",
            required=True,
        ),
        OpenApiParameter(
            name="id",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the user discount",
            required=True,
        ),
    ]
)
class NestedDiscountRedemptionViewSet(NestedViewSetMixin, ModelViewSet):
    """API view set for Discount Redemptions"""

    serializer_class = DiscountRedemptionSerializer
    queryset = DiscountRedemption.objects.all()
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser,)
    pagination_class = LimitOffsetPagination


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="parent_lookup_discount",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the parent discount",
            required=True,
        ),
        OpenApiParameter(
            name="id",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the user discount",
            required=True,
        ),
    ]
)
class NestedUserDiscountViewSet(NestedViewSetMixin, ModelViewSet):
    """
    API view set for User Discounts. This one is for use within a Discount.
    """

    serializer_class = UserDiscountMetaSerializer
    queryset = UserDiscount.objects.all()
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser,)
    pagination_class = LimitOffsetPagination

    def create(self, request, **kwargs):
        """Create an association between a user and a discount."""

        discount = Discount.objects.get(pk=kwargs["parent_lookup_discount"])

        UserDiscount.objects.create(discount=discount, user_id=request.data["user"])

        return Response(
            UserDiscountMetaSerializer(
                UserDiscount.objects.filter(discount=discount).all(), many=True
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, **kwargs):
        """Partial update for a user discount."""

        discount = Discount.objects.get(pk=kwargs["parent_lookup_discount"])

        (_, created) = UserDiscount.objects.get_or_create(
            discount=discount, user_id=request.data["user"]
        )

        return Response(
            UserDiscountMetaSerializer(
                UserDiscount.objects.filter(discount=discount).all(), many=True
            ).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def destroy(self, request, **kwargs):  # noqa: ARG002
        """Delete a user discount."""

        discount = Discount.objects.get(pk=kwargs["parent_lookup_discount"])
        user = User.objects.get(pk=kwargs["pk"])

        UserDiscount.objects.filter(discount=discount, user=user).delete()

        return Response(
            UserDiscountMetaSerializer(
                UserDiscount.objects.filter(discount=discount).all(), many=True
            ).data
        )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="parent_lookup_discount",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the parent discount",
            required=True,
        ),
        OpenApiParameter(
            name="id",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the user discount",
            required=True,
        ),
    ]
)
class NestedDiscountTierViewSet(NestedViewSetMixin, ModelViewSet):
    """
    API view set for Flexible Pricing Tiers. This one is for use within a Discount.
    """

    serializer_class = FlexiblePriceTierSerializer
    queryset = FlexiblePriceTier.objects.all()
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser,)
    pagination_class = LimitOffsetPagination


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="parent_lookup_discount",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the parent discount",
            required=True,
        ),
        OpenApiParameter(
            name="id",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the user discount",
            required=True,
        ),
    ]
)
class UserDiscountViewSet(ModelViewSet):
    """API view set for User Discounts. This one is for working with the set as a whole."""

    serializer_class = UserDiscountSerializer
    queryset = UserDiscount.objects.all()
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser,)
    pagination_class = LimitOffsetPagination


class OrderHistoryPagination(LimitOffsetPagination):
    """
    Sets a default limit for the order history API.

    Without a default, DRF skips pagination when the caller omits `limit` and
    returns a bare list instead of the `{count, next, previous, results}` envelope
    the generated spec declares.
    """

    default_limit = 20


@extend_schema_view(
    list=extend_schema(
        description=("Retrives the current user's order history."),
        parameters=[],
    ),
    retrieve=extend_schema(
        description="Retrieve a historical order for the current user.",
        parameters=[
            OpenApiParameter("id", OpenApiTypes.INT, OpenApiParameter.PATH),
        ],
    ),
)
class OrderHistoryViewSet(ReadOnlyModelViewSet):
    """Viewset to retrieve a user's order history."""

    serializer_class = OrderHistorySerializer
    pagination_class = OrderHistoryPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only the user's fulfilled or refunded orders."""
        return (
            Order.objects.filter(purchaser=self.request.user)
            .filter(state__in=[OrderStatus.FULFILLED, OrderStatus.REFUNDED])
            # Every serialized order reads both, once per row.
            .prefetch_related("refund_requests", "lines__purchased_object")
            .order_by("-created_on")
            .all()
        )


class OrderReceiptView(RetrieveAPIView):
    """Viewset to retrieve an order so it can be viewed as a receipt."""

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only the user's orders"""
        return Order.objects.filter(purchaser=self.request.user).all()


class ReceiptByRunView(LoginRequiredMixin, View):
    """Redirects to the receipt page for an order associated with a course run."""

    def get(self, request, run_id):
        """Look up the receipt for the given course run and redirect to it."""
        paid_run = (
            PaidCourseRun.objects.filter(
                user=request.user,
                course_run_id=run_id,
                order__state=OrderStatus.FULFILLED,
            )
            .order_by("-created_on")
            .first()
        )
        if paid_run is None:
            raise Http404
        return redirect(f"/orders/receipt/{paid_run.order_id}/")


class ReceiptByProgramView(LoginRequiredMixin, View):
    """Redirects to the receipt page for an order associated with a program."""

    def get(self, request, program_id):
        """Look up the receipt for the given program and redirect to it."""
        paid_program = (
            PaidProgram.objects.filter(
                user=request.user,
                program_id=program_id,
                order__state=OrderStatus.FULFILLED,
            )
            .order_by("-created_on")
            .first()
        )
        if paid_program is None:
            raise Http404
        return redirect(f"/orders/receipt/{paid_program.order_id}/")


@extend_schema(
    description=("Pollable interface to determine status of a particular order."),
    methods=["GET"],
    request=None,
    responses=OrderStatusSerializer,
    parameters=[
        OpenApiParameter(
            "order_id", OpenApiTypes.STR, OpenApiParameter.PATH, required=True
        ),
    ],
)
@api_view(["GET"])
@permission_classes(
    [
        IsAuthenticated,
    ]
)
def get_order_status(request, order_id: str):
    """
    Return the status of the specified order.

    This is to support payment processors that don't necessarily give us an
    immediate decision on order status - the frontend can poll this to see if
    the order has gone through or not.
    """

    order = Order.objects.filter(purchaser=request.user)

    if order_id.isnumeric():
        order = order.filter(pk=order_id)
    else:
        order = order.filter(reference_number=order_id)

    try:
        order = order.get()
    except Order.DoesNotExist:
        return Response({"state": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(OrderStatusSerializer(order).data)


@extend_schema(
    description="Submit a refund request for a fulfilled order. Only the order's purchaser may submit a request, and B2B contract orders are excluded.",
    request=RefundRequestSerializer,
    responses={201: RefundRequestSerializer},
)
class RefundRequestView(CreateAPIView):
    """Accept and store a learner-submitted refund request, then notify customer service."""

    serializer_class = RefundRequestSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        instance = serializer.save()
        send_refund_request_notification_email.delay(instance.id)
