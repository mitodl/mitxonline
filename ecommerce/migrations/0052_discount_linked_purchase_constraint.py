from django.contrib.postgres.operations import (
    AddConstraintNotValid,
    ValidateConstraint,
)
from django.db import migrations, models


class Migration(migrations.Migration):
    # NOT VALID + VALIDATE keeps the ACCESS EXCLUSIVE lock momentary:
    # ecommerce_discount holds bulk-generated codes and prod has no
    # statement_timeout, so a blocked full-table validation would queue
    # against live checkout indefinitely.
    atomic = False

    dependencies = [
        ("ecommerce", "0051_discountredemption_source_line"),
    ]

    operations = [
        AddConstraintNotValid(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=~models.Q(discount_type="linked-purchase")
                | models.Q(redemption_type="linked-purchase"),
                name="linked_purchase_discount_type_requires_redemption_type",
            ),
        ),
        ValidateConstraint(
            model_name="discount",
            name="linked_purchase_discount_type_requires_redemption_type",
        ),
    ]
