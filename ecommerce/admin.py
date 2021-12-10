from django.contrib import admin
from ecommerce.models import Product
from reversion.admin import VersionAdmin

@admin.register(Product)
class ProductAdmin(VersionAdmin):
    """Admin for Product"""

    model = Product
    search_fields = ["description", "price"]
    list_display = ["id", "description", "price"]