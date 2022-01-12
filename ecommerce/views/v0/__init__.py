"""
MITxOnline ecommerce views
"""
import logging
from django.http import HttpResponseRedirect
from django.urls import reverse
from rest_framework.decorators import permission_classes, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet, ModelViewSet
from rest_framework.pagination import LimitOffsetPagination
from django.db.models import Q, Count
from mitol.common.utils import now_in_utc
from rest_framework_extensions.mixins import NestedViewSetMixin

from courses.models import (
    CourseRun,
    Course,
    Program,
    ProgramRun,
)

from ecommerce.serializers import ProductSerializer, BasketSerializer, BasketItemSerializer
from ecommerce.models import Product, Basket, BasketItem

log = logging.getLogger(__name__)


class ProductsPagination(LimitOffsetPagination):
    default_limit = 2
    limit_query_param = "l"
    offset_query_param = "o"
    max_limit = 50


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
            .exclude(is_active__exact=False)
            .select_related("content_type")
            .prefetch_related("purchasable_object")
        )


class BasketViewSet(NestedViewSetMixin, ModelViewSet):
    """API view set for Basket"""
    queryset = Basket.objects.all()
    serializer_class = BasketSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        basket = self.get_object()
        product_id = request.data.get("product_id")
        serializer = BasketSerializer(basket)
        return Response(serializer.data)


class BasketItemViewSet(NestedViewSetMixin, ModelViewSet):
    """API view set for BasketItem"""
    queryset = BasketItem.objects.all()
    serializer_class = BasketItemSerializer
    permission_classes = [IsAuthenticated]


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_product_to_basket_view(request):
    """View to handle direct POST requests to enroll in a course run"""
    user = request.user
    product_id_str = request.data.get("product_id")
    if product_id_str is not None and product_id_str.isdigit():
        product = (
            Product.objects.filter(id=int(product_id_str)).first()
        )
    else:
        product = None
    if product is None:
        log.error(
            "Attempting to add in a non-existent product (id: %s)", str(product_id_str)
        )
        return HttpResponseRedirect(request.headers["Referer"]), None, None
    basket, _ = Basket.objects.get_or_create(user=user)
    item, created = BasketItem.objects.update_or_create(basket=basket, product=product)
    if created is False:
        item.quantity += 1
        item.save()

    return HttpResponseRedirect(reverse("user-dashboard"))
