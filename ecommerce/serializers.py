"""
MITxOnline ecommerce serializers
"""
from rest_framework import serializers

from ecommerce import models
from courses.models import CourseRun, ProgramRun


class ProgramRunProductPurchasableObjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramRun
        fields = [
            "id",
            "run_tag",
            "start_date",
            "end_date",
        ]


class CourseRunProductPurchasableObjectSerializer(serializers.ModelSerializer):
    course = serializers.SerializerMethodField()
    readable_id = serializers.CharField(source="text_id")

    def get_course(self, instance):
        return {"id": instance.course.id, "title": instance.course.title}

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


class ProductSerializer(serializers.ModelSerializer):
    purchasable_object = ProductPurchasableObjectField(read_only=True)

    class Meta:
        fields = [
            "id",
            "price",
            "description",
            "purchasable_object",
            "is_active",
        ]
        model = models.Product


class BasketItemSerializer(serializers.ModelSerializer):
    """BasketItem model serializer"""

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
