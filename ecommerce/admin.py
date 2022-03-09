from django.contrib import admin
from ecommerce.models import BasketDiscount, Product, Basket, BasketItem, Transaction
from django.contrib.admin.decorators import display
from fsm_admin.mixins import FSMTransitionMixin
from reversion.admin import VersionAdmin
from mitol.common.admin import TimestampedModelAdmin

from ecommerce.models import (
    Product,
    Discount,
    UserDiscount,
    DiscountRedemption,
    Order,
    PendingOrder,
    CanceledOrder,
    FulfilledOrder,
    RefundedOrder,
    Line,
    BasketDiscount,
)


@admin.register(Product)
class ProductAdmin(VersionAdmin):
    """Admin for Product"""

    model = Product
    search_fields = ["description", "price"]
    list_display = ["id", "description", "price"]


@admin.register(Basket)
class BasketAdmin(VersionAdmin):
    """Admin for Basket"""

    model = Basket
    search_fields = ["user"]
    list_display = ["id", "user"]


@admin.register(BasketItem)
class BasketItemAdmin(VersionAdmin):
    """Admin for BasketItem"""

    model = BasketItem
    search_fields = ["product"]
    list_display = ["id", "product", "quantity"]


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    model = Discount
    search_fields = ["discount_type", "redemption_type"]
    list_display = ["id", "discount_type", "amount", "redemption_type"]


@admin.register(UserDiscount)
class UserDiscountAdmin(admin.ModelAdmin):
    model = UserDiscount
    search_fields = ["discount", "user"]
    list_display = ["id", "discount", "user"]


@admin.register(DiscountRedemption)
class DiscountRedemptionAdmin(admin.ModelAdmin):
    model = DiscountRedemption
    search_fields = ["redemption_date", "redeemed_discount", "redeemed_by"]
    list_display = ["id", "redemption_date", "redeemed_discount", "redeemed_by"]


@admin.register(BasketDiscount)
class BasketDiscountAdmin(admin.ModelAdmin):
    model = BasketDiscount
    list_display = ["id", "redeemed_basket", "redeemed_discount"]


class OrderLineInline(admin.TabularInline):
    """Inline editor for lines"""

    model = Line
    readonly_fields = ["unit_price", "total_price", "discounted_price"]
    min_num = 1
    extra = 0


class OrderDiscountInline(admin.TabularInline):
    """Inline editor for DiscountRedemptions in an Order"""

    model = DiscountRedemption
    readonly_fields = ["redemption_date", "redeemed_by", "redeemed_discount"]
    min_num = 0
    extra = 0


class OrderTransactionInline(admin.TabularInline):
    """Inline editor for transactions for an Order"""

    def has_add_permission(self, request, obj=None):
        return False

    model = Transaction
    readonly_fields = ["order", "amount", "data"]
    min_num = 0
    extra = 0
    can_delete = False
    can_add = False


class BaseOrderAdmin(FSMTransitionMixin, TimestampedModelAdmin):
    """Base admin for Order"""

    search_fields = ["id", "purchaser__email", "purchaser__username"]
    list_display = ["id", "state", "get_purchaser", "total_price_paid"]
    list_fields = ["state"]
    list_filter = ["state"]
    inlines = [OrderLineInline, OrderDiscountInline, OrderTransactionInline]

    @display(description="Purchaser")
    def get_purchaser(self, obj: Order):
        return f"{obj.purchaser.name} ({obj.purchaser.email})"

    def get_queryset(self, request):
        """Filter only to pending orders"""
        return (
            super()
            .get_queryset(request)
            .prefetch_related("purchaser", "lines__product_version")
        )


@admin.register(Order)
class OrderAdmin(BaseOrderAdmin):
    """Admin for Order"""

    model = Order


@admin.register(PendingOrder)
class PendingOrderAdmin(BaseOrderAdmin):
    """Admin for PendingOrder"""

    model = PendingOrder

    def get_queryset(self, request):
        """Filter only to pending orders"""
        return super().get_queryset(request).filter(state=Order.STATE.PENDING)


@admin.register(CanceledOrder)
class CanceledOrderAdmin(BaseOrderAdmin):
    """Admin for CanceledOrder"""

    model = CanceledOrder

    def get_queryset(self, request):
        """Filter only to canceled orders"""
        return super().get_queryset(request).filter(state=Order.STATE.CANCELED)


@admin.register(FulfilledOrder)
class FulfilledOrderAdmin(BaseOrderAdmin):
    """Admin for FulfilledOrder"""

    model = FulfilledOrder

    def get_queryset(self, request):
        """Filter only to fulfilled orders"""
        return super().get_queryset(request).filter(state=Order.STATE.FULFILLED)


@admin.register(RefundedOrder)
class RefundedOrderAdmin(BaseOrderAdmin):
    """Admin for RefundedOrder"""

    model = RefundedOrder

    def get_queryset(self, request):
        """Filter only to refunded orders"""
        return super().get_queryset(request).filter(state=Order.STATE.REFUNDED)
