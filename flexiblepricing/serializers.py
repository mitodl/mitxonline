from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from courses.models import Course, Program
from courses.serializers import BaseCourseSerializer, BaseProgramSerializer
from ecommerce.models import Discount
from ecommerce.serializers import DiscountSerializer
from flexiblepricing import models
from users.serializers import UserSerializer


class CurrencyExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CurrencyExchangeRate
        fields = [
            "id",
            "currency_code",
            "exchange_rate",
        ]


class CountryIncomeThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CountryIncomeThreshold
        fields = ["id", "country_code", "income_threshold"]


class FlexiblePriceTierSerializer(serializers.ModelSerializer):
    courseware_object = serializers.SerializerMethodField()

    class Meta:
        model = models.FlexiblePriceTier
        fields = [
            "id",
            "courseware_object",
            "discount",
            "current",
            "income_threshold_usd",
        ]

    def get_courseware_object(self, instance):
        if instance.courseware_content_type.model == "course":
            return BaseCourseSerializer(instance=instance.courseware_object).data
        else:
            return BaseProgramSerializer(instance=instance.courseware_object).data


class FlexiblePriceSerializer(serializers.ModelSerializer):
    """
    Serializer for flexible price requests
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = models.FlexiblePrice
        fields = [
            "id",
            "user",
            "status",
            "income_usd",
            "original_income",
            "original_currency",
            "country_of_income",
            "date_exchange_rate",
            "date_documents_sent",
            "justification",
            "country_of_residence",
        ]


class FlexiblePriceIncomeSerializer(serializers.ModelSerializer):
    """
    Financial Assistance Requests income serializer
    """

    class Meta:
        model = models.FlexiblePrice
        fields = [
            "income_usd",
            "original_income",
            "original_currency",
        ]


class FlexiblePriceAdminSerializer(serializers.ModelSerializer):
    """
    Serializer for Financial Assistance Requests
    """

    COURSEWARE_SERIALIZER_CLASSES = {
        Course: BaseCourseSerializer,
        Program: BaseProgramSerializer,
    }

    courseware = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    income = serializers.SerializerMethodField()
    user = UserSerializer(read_only=True)
    applicable_discounts = serializers.SerializerMethodField()

    class Meta:
        model = models.FlexiblePrice
        fields = [
            "id",
            "user",
            "status",
            "country_of_income",
            "date_exchange_rate",
            "date_documents_sent",
            "justification",
            "country_of_residence",
            "courseware",
            "discount",
            "applicable_discounts",
            "income",
        ]

    def update(self, instance, validated_data):
        """
        Updates Flexible price tier if staff has changed the discount while approving a financial assistance request.
        """
        selected_discount = self.initial_data.get("discount", None)
        discount_id = selected_discount.get("id", None) if selected_discount else None

        if discount_id and discount_id != instance.tier.discount_id:
            courseware_content_type = ContentType.objects.get_for_model(
                instance.courseware_object
            )
            flexible_price_tier = models.FlexiblePriceTier.objects.filter(
                current=True,
                courseware_content_type=courseware_content_type,
                courseware_object_id=instance.courseware_object_id,
                discount_id=discount_id,
            ).first()
            instance.tier = flexible_price_tier

        return super().update(instance, validated_data)

    def get_courseware(self, instance):
        """
        Returns serialized courseware object.
        """
        courseware_content_type = ContentType.objects.get_for_model(
            instance.courseware_object
        )
        courseware_serializer_class = self.COURSEWARE_SERIALIZER_CLASSES.get(
            courseware_content_type.model_class(), None
        )
        if courseware_serializer_class:
            return courseware_serializer_class(instance=instance.courseware_object).data

        return None

    def get_discount(self, instance):
        """
        Returns applied discount information for a Financial Assistance Request.
        """
        return DiscountSerializer(instance=instance.tier.discount).data

    def get_applicable_discounts(self, instance):
        """
        Returns discount options for a Financial Assistance Request.
        """
        courseware_content_type = ContentType.objects.get_for_model(
            instance.courseware_object
        )
        discounts = Discount.objects.filter(
            flexible_price_tiers__current=True,
            flexible_price_tiers__courseware_content_type=courseware_content_type,
            flexible_price_tiers__courseware_object_id=instance.courseware_object_id,
        )

        return DiscountSerializer(
            discounts,
            many=True,
        ).data

    def get_income(self, instance):
        """
        Returns income information associated with a flexible price request.
        """
        return FlexiblePriceIncomeSerializer(instance=instance).data


class FlexiblePriceCoursewareAdminSerializer(serializers.ModelSerializer):
    """
    Serializer for coursewares in flexible price requests
    """

    id = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    readable_id = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()

    def get_courseware_object(self, instance):
        course_content_type = ContentType.objects.get(
            app_label="courses", model="course"
        ).id
        program_content_type = ContentType.objects.get(
            app_label="courses", model="program"
        ).id
        if instance["courseware_content_type"] == course_content_type:
            return BaseCourseSerializer(
                Course.objects.filter(id=instance["courseware_object_id"]).first()
            ).data
        elif instance["courseware_content_type"] == program_content_type:
            return BaseProgramSerializer(
                Program.objects.filter(id=instance["courseware_object_id"]).first()
            ).data

    def get_id(self, instance):
        """
        Returns serialized courseware id.
        """
        return self.get_courseware_object(instance)["id"]

    def get_type(self, instance):
        """
        Returns serialized courseware type.
        """
        return self.get_courseware_object(instance)["type"]

    def get_readable_id(self, instance):
        """
        Returns serialized courseware readable id.
        """
        return self.get_courseware_object(instance)["readable_id"]

    def get_title(self, instance):
        """
        Returns serialized courseware title.
        """
        return self.get_courseware_object(instance)["title"]

    class Meta:
        model = models.FlexiblePrice
        fields = ["id", "title", "readable_id", "type"]
