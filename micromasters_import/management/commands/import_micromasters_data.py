"""
Imports Micromasters data
"""
from dataclasses import dataclass
import os

from django.conf import settings
from django.core.management import BaseCommand
from django.db import connection


SQL_FILES_DIR = os.path.join(
    settings.BASE_DIR, "micromasters_import/management/commands/queries/"
)


class Command(BaseCommand):
    """
    Imports Micromasters data
    """

    @dataclass
    class Sql:
        file_name: str
        raw_sql: str

    help = "Imports Micromasters data"

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        sqls = []

        self.stdout.write(f"Gathering SQL queries:")

        for root, _, files in os.walk(SQL_FILES_DIR):
            for file_name in sorted(files):
                with open(os.path.join(root, file_name), "r") as sql_file:
                    self.stdout.write(file_name)
                    sqls.append(self.Sql(file_name, sql_file.read()))

        proceed = input(f"Found {len(sqls)} queries. Proceed? (y/n)")

        if proceed.lower() != "y":
            self.stdout.write(self.style.ERROR("Aborting operation"))
            exit(1)

        with connection.cursor() as cursor:
            self.stdout.write(self.style.SUCCESS("Connected to database"))

            for sql in sqls:
                self.stdout.write("=" * 20)

                self.stdout.write(f"Running: {sql.file_name}")

                self.stdout.write("-" * 20)
                self.stdout.write(f"Executing SQL:")
                self.stdout.write(sql.raw_sql)
                self.stdout.write("-" * 20)

                cursor.execute(sql.raw_sql)

                self.stdout.write(f"Rows added/updated: {cursor.rowcount}")
                self.stdout.write("=" * 20)

        self.stdout.write(self.style.SUCCESS("Successfully imported MicroMasters data"))
