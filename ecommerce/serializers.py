"""
MITxOnline ecommerce serializers
"""
from this import d
from rest_framework import serializers

from ecommerce import models
from courses.models import CourseRun, ProgramRun, Course
from ecommerce.models import Basket, Product, BasketItem

from cms.serializers import CoursePageSerializer
from users.serializers import UserSerializer


class ProgramRunProductPurchasableObjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramRun
        fields = [
            "id",
            "run_tag",
            "start_date",
            "end_date",
        ]


class CoursePageObjectField(serializers.RelatedField):
    def to_representation(self, value):
        return CoursePageSerializer(instance=value).data


class CourseProductPurchasableObjectSerializer(serializers.ModelSerializer):
    page = CoursePageObjectField(read_only=True)

    class Meta:
        model = Course
        fields = ["id", "title", "page"]


class CourseRunProductPurchasableObjectSerializer(serializers.ModelSerializer):
    course = CourseProductPurchasableObjectSerializer(read_only=True)
    readable_id = serializers.CharField(source="text_id")

    class Meta:
        model = CourseRun
        fields = [
            "id",
            "title",
            "run_tag",
            "start_date",
            "end_date",
            "course",
            "readable_id",
            "enrollment_start",
            "enrollment_end",
        ]


class ProductPurchasableObjectField(serializers.RelatedField):
    def to_representation(self, value):
        """Serialize the purchasable object using a serializer that matches the model type (either a Program Run or a Course Run)"""
        if isinstance(value, ProgramRun):
            return ProgramRunProductPurchasableObjectSerializer(instance=value).data
        elif isinstance(value, CourseRun):
            return CourseRunProductPurchasableObjectSerializer(instance=value).data
        raise Exception(
            "Unexpected to find type for Product.purchasable_object:", value.__class__
        )


class BaseProductSerializer(serializers.ModelSerializer):
    """Simple serializer for Product without related purchasable objects"""

    class Meta:
        fields = [
            "id",
            "price",
            "description",
            "is_active",
        ]
        model = models.Product


class ProductSerializer(BaseProductSerializer):
    purchasable_object = ProductPurchasableObjectField(read_only=True)

    class Meta:
        fields = BaseProductSerializer.Meta.fields + [
            "purchasable_object",
        ]
        model = models.Product


class BasketItemSerializer(serializers.ModelSerializer):
    """BasketItem model serializer"""

    def perform_create(self, validated_data):
        basket = Basket.objects.get(user=validated_data["user"])
        product = Product.objects.get(id=validated_data["product"])
        item, _ = BasketItem.objects.get_or_create(basket=basket, product=product)
        return item

    class Meta:
        model = models.BasketItem
        fields = [
            "basket",
            "product",
            "id",
        ]


class BasketSerializer(serializers.ModelSerializer):
    """Basket model serializer"""

    basket_items = serializers.SerializerMethodField()

    def get_basket_items(self, instance):
        """Get items in the basket"""
        return [
            BasketItemSerializer(instance=basket, context=self.context).data
            for basket in instance.basket_items.all()
        ]

    class Meta:
        fields = [
            "id",
            "user",
            "basket_items",
        ]
        model = models.Basket


class BasketItemWithProductSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    def get_product(self, instance):
        return ProductSerializer(instance=instance.product, context=self.context).data

    class Meta:
        model = models.BasketItem
        fields = [
            "basket",
            "product",
            "id",
        ]


class BasketWithProductSerializer(serializers.ModelSerializer):
    basket_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    def get_basket_items(self, instance):
        return [
            BasketItemWithProductSerializer(instance=basket, context=self.context).data
            for basket in instance.basket_items.all()
        ]

    def get_total_price(self, instance):
        return sum(
            product.price
            for product in [item.product for item in instance.basket_items.all()]
        )

    class Meta:
        fields = ["id", "user", "basket_items", "total_price"]
        model = models.Basket


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        fields = [
            "id",
            "state",
            "purchaser",
            "total_price_paid",
            "lines",
        ]
        model = models.Order


class LineSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    def get_product(self, instance):
        product = models.Product.objects.get(
            pk=instance.product_version.field_dict["id"]
        )

        return ProductSerializer(instance=product).data

    class Meta:
        fields = [
            "quantity",
            "item_description",
            "content_type",
            "unit_price",
            "total_price",
            "id",
            "product",
        ]
        model = models.Line


class OrderHistorySerializer(serializers.ModelSerializer):
    titles = serializers.SerializerMethodField()
    lines = LineSerializer(many=True)

    def get_titles(self, instance):
        titles = []

        for line in instance.lines.all():
            product = models.Product.objects.get(
                pk=line.product_version.field_dict["id"]
            )
            if product.content_type.model == "courserun":
                titles.append(product.purchasable_object.course.title)
            elif product.content_type.model == "programrun":
                titles.append(product.description)
            else:
                titles.append(f"No Title - {product.id}")

        return titles

    class Meta:
        fields = [
            "id",
            "state",
            "reference_number",
            "purchaser",
            "total_price_paid",
            "lines",
            "created_on",
            "titles",
        ]
        model = models.Order
        depth = 1
