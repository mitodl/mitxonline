from django.contrib import admin
from ecommerce.models import Product, Discount, UserDiscount, DiscountRedemption
from reversion.admin import VersionAdmin


@admin.register(Product)
class ProductAdmin(VersionAdmin):
    """Admin for Product"""

    model = Product
    search_fields = ["description", "price"]
    list_display = ["id", "description", "price"]


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
