from rest_framework import serializers

from b2b.models import DiscountContractAttachmentRedemption


class AssignedCodeSerializer(serializers.ModelSerializer):
    class OrderReceiptSerializer(serializers.ModelSerializer):
        """
        Serializer for extracting receipt info from an Order object
        This hews pretty closely to the data format in xPro but modified a bit
        for MITxOnline's data model.
        """

        lines = serializers.SerializerMethodField()
        purchaser = serializers.SerializerMethodField()
        coupon = serializers.SerializerMethodField()
        order = serializers.SerializerMethodField()
        receipt = serializers.SerializerMethodField()

        class Meta:
            fields = ["purchaser", "lines", "coupon", "order", "receipt"]
            model = DiscountContractAttachmentRedemption
