from django.core.management.base import BaseCommand

from flexiblepricing.api import import_country_income_thresholds


class Command(BaseCommand):
    """
    Import a csv of country income thresholds
    """

    help = __doc__

    def add_arguments(self, parser):
        """Handle arguments"""
        parser.add_argument("csv_path", type=str, help="path to the csv")

    def handle(self, *args, **options):  # noqa: ARG002
        """Import a csv of country income thresholds"""
        import_country_income_thresholds(options["csv_path"])
