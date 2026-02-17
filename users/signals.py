from django.db.models.signals import post_save
from django.dispatch import receiver

from hubspot_sync.task_helpers import sync_hubspot_user
from users.models import User


@receiver(post_save, sender=User, dispatch_uid="user_post_save_hubspot_sync")
def sync_user_to_hubspot_on_create(sender, instance, created, **kwargs):  # noqa: ARG001
    """
    Sync newly created users to Hubspot.

    """
    if created:
        sync_hubspot_user(instance)
