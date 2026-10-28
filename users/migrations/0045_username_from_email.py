"""Set username to the email for users whose username is something else."""

from django.db import migrations
from django.db.models import Exists, F, OuterRef, Q
from django.db.models.functions import Lower

UPDATE_BATCH_SIZE = 5000


def username_from_email(apps, schema_editor):
    """
    Set username = email for every user where that can't collide.

    Keycloak's username in the olapps realm is the email, and scim-for-keycloak
    finds a user it has no stored id for with `userName eq "<email>"`. A user
    whose username is still a pre-Keycloak handle can't be found that way, so
    their SCIM operations fail with a 409 and retry indefinitely.

    A user is skipped when their email is already another user's username, so
    the unique constraint can't be violated. Those rows need manual review.
    """
    User = apps.get_model("users", "User")
    others = User.objects.exclude(pk=OuterRef("pk"))
    user_ids = list(
        User.objects.annotate(
            lower_username=Lower("username"), lower_email=Lower("email")
        )
        .exclude(Q(email="") | Q(lower_username=F("lower_email")))
        .exclude(
            Exists(
                others.annotate(lower_username=Lower("username")).filter(
                    lower_username=OuterRef("lower_email")
                )
            )
        )
        .values_list("pk", flat=True)
    )
    for start in range(0, len(user_ids), UPDATE_BATCH_SIZE):
        User.objects.filter(pk__in=user_ids[start : start + UPDATE_BATCH_SIZE]).update(
            username=F("email")
        )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0044_alter_user_b2b_contracts"),
    ]

    # The old usernames aren't kept, so this can't be reversed.
    operations = [migrations.RunPython(username_from_email, migrations.RunPython.noop)]
