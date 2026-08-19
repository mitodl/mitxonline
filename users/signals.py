from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from hubspot_sync.task_helpers import sync_hubspot_user
from users.models import LegalAddress, User


@receiver(post_save, sender=User, dispatch_uid="user_post_save_hubspot_sync")
def sync_user_to_hubspot_on_create(sender, instance, created, **kwargs):  # noqa: ARG001
    """
    Sync newly created users to Hubspot.

    """
    if created:
        transaction.on_commit(lambda: sync_hubspot_user(instance))


@receiver(post_save, sender=LegalAddress, dispatch_uid="legal_address_post_save_hubspot_sync")
def sync_user_to_hubspot_on_legal_address_save(sender, instance, **kwargs):  # noqa: ARG001
    """
    Re-sync the associated user to HubSpot when their legal address is saved.

    This ensures that first_name and last_name are present in HubSpot even when
    the LegalAddress is created or updated after the initial user sync.
    """
    transaction.on_commit(lambda: sync_hubspot_user(instance.user))
