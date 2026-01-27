import time

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand
from django.db import connection, models
from django.utils import timezone


class Command(BaseCommand):
    """
    Deletes expired OAuth2 access tokens in chunks to avoid long-running transactions.
    """

    def add_arguments(self, parser):
        """Parses command line arguments."""

        parser.add_argument(
            "--batch-size",
            help="How many records to delete at once.",
            type=int,
        )
        parser.add_argument(
            "--execute",
            help="If provided, actually delete the tokens instead of just reporting how many would be deleted.",
            action="store_true",
        )
        parser.add_argument(
            "--sleep",
            help="If provided, sleep this many seconds between batches.",
            type=float,
            default=0.0,
        )

    def get_access_token_model(self):
        """Return the AccessToken model that is active in this project."""
        return apps.get_model(settings.OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL)

    def get_min_and_max_id(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT MIN(id) as min_id, MAX(id) as max_id FROM oauth2_provider_accesstoken"
            )
            return cursor.fetchone()

    def handle(self, *args, **kwargs):  # noqa: ARG002
        batch_size = kwargs["batch_size"]
        execute = kwargs["execute"]
        sleep = kwargs["sleep"]
        access_token_model = self.get_access_token_model()
        min_id, max_id = self.get_min_and_max_id()
        lower_id = min_id
        upper_id = min_id + batch_size
        now = timezone.now()
        total_deleted = 0
        # We always attempt to loop through the whole table.
        # There's no harm in executing up to one final empty query
        while lower_id < max_id:
            self.stdout.write(
                f"Querying for tokens with IDs between {lower_id} and {upper_id}"
            )
            deletion_queryset = access_token_model.objects.filter(
                models.Q(refresh_token__isnull=True, expires__lt=now),
                id__gte=lower_id,
                id__lt=upper_id,
            )

            if execute:
                batch_delete_count = deletion_queryset.delete()
                self.stdout.write(f"Deleted {batch_delete_count[0]} records")
                total_deleted += batch_delete_count[0]
            else:
                self.stdout.write(
                    f"Would delete tokens: {list(deletion_queryset.values_list('id', flat=True))}"
                )

            lower_id = upper_id
            upper_id = lower_id + batch_size
            time.sleep(sleep)

        self.stdout.write(self.style.SUCCESS(f"Deleted {total_deleted} records"))
