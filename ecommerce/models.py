from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from mitol.common.models import TimestampedModel
import reversion


def valid_purchasable_objects_list():
    return models.Q(app_label="courses", model="courserun") | models.Q(
        app_label="courses", model="programrun"
    )


@reversion.register(exclude=("content_type", "object_id", "created_on", "updated_on"))
class Product(TimestampedModel):
    """
    Representation of a purchasable product. There is a GenericForeignKey to a
    Course Run or Program Run.
    """

    valid_purchasable_objects = valid_purchasable_objects_list()
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=valid_purchasable_objects,
    )
    object_id = models.PositiveIntegerField()
    purchasable_object = GenericForeignKey("content_type", "object_id")

    price = models.DecimalField(max_digits=7, decimal_places=2, help_text="")
    description = models.TextField()
    is_active = models.BooleanField(
        default=True,
        null=False,
        help_text="Controls visibility of the product in the app.",
    )

    def __str__(self):
        return f"{self.description} {self.price}"
