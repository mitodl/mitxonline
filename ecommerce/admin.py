from django.contrib import admin
from ecommerce.models import Product


class ProductAdmin(admin.ModelAdmin):
    """Admin for Product"""

    model = Product
    search_fields = ["description", "price"]
    list_display = ["id", "description", "price"]


admin.site.register(Product, ProductAdmin)
