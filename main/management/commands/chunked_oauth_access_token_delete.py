from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    """
    Bootstraps a fresh MITxOnline instance.
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

    def get_refresh_token_model(self):
        return apps.get_model(settings.OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL)

    def get_access_token_model(self):
        """Return the AccessToken model that is active in this project."""
        return apps.get_model(settings.OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL)

    def get_min_and_max_id(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT MIN(id), MAX(id) as min_id FROM oauth2_provider_accesstoken"
            )
            return cursor.fetchone()

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Coordinates the other commands."""

        batch_size = kwargs["batch_size"]
        execute = kwargs["execute"]
        access_token_model = self.get_access_token_model()
        refresh_token_model = self.get_refresh_token_model()
        # Quick and dirty, get the minimum ID to start from. This is the literal table name in prod.
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
            # Annoyingly, we need to check against another table (the refresh token table) to see
            # if a token has an associated refresh token. This is why the original script has uses a Q expression
            # However, that table is _much_ smaller than the access token table, so we will just make
            # multiple queries, do the accounting in Python and run the delete by ID knowing that the vast majority of refresh token queries will be empty
            potential_deletion_ids = set(
                access_token_model.objects.filter(
                    id__gt=lower_id, id__lte=upper_id, expires__lt=now
                ).values_list("id", flat=True)
            )

            # Now filter out any tokens that have a matching refresh token
            refresh_token_qs = set(
                refresh_token_model.objects.filter(
                    access_token_id__in=potential_deletion_ids
                ).values_list("access_token_id", flat=True)
            )
            token_ids_to_delete = potential_deletion_ids - refresh_token_qs

            if execute:
                batch_delete_count = access_token_model.objects.filter(
                    id__in=token_ids_to_delete
                ).delete()
                self.stdout.write(f"Deleted {batch_delete_count} records")
                total_deleted += batch_delete_count
            else:
                self.stdout.write(f"Would delete tokens: {token_ids_to_delete}")

            lower_id = upper_id
            upper_id = lower_id + batch_size
