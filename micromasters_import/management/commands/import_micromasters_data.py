"""
Imports Micromasters data
"""

import os
from dataclasses import dataclass

from django.conf import settings
from django.core.management import BaseCommand
from django.db import connection

SQL_FILES_DIR = os.path.join(  # noqa: PTH118
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

    help = "Imports Micromasters data. Specify --num to run a paticular file. e.g. --num 002"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--num",
            type=str,
            help="specify a file num to run. eg. 002 refers to 002_import_courserun.sql",
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG002
        file_num = kwargs["num"].zfill(3)
        sqls = []

        self.stdout.write("Gathering SQL queries:")

        for root, _, files in os.walk(SQL_FILES_DIR):
            for file_name in sorted(files):
                if file_num and not file_name.startswith(file_num):
                    continue
                with open(os.path.join(root, file_name)) as sql_file:  # noqa: PTH118, PTH123
                    self.stdout.write(file_name)
                    sqls.append(self.Sql(file_name, sql_file.read()))

        proceed = input(f"Found {len(sqls)} queries. Proceed? (y/n)")

        if proceed.lower() != "y":
            self.stdout.write(self.style.ERROR("Aborting operation"))
            exit(1)  # noqa: PLR1722

        with connection.cursor() as cursor:
            self.stdout.write(self.style.SUCCESS("Connected to database"))

            for sql in sqls:
                self.stdout.write("=" * 20)

                self.stdout.write(f"Running: {sql.file_name}")

                self.stdout.write("-" * 20)
                self.stdout.write("Executing SQL:")
                self.stdout.write(sql.raw_sql)
                self.stdout.write("-" * 20)

                cursor.execute(sql.raw_sql)

                self.stdout.write(f"Rows added/updated: {cursor.rowcount}")
                self.stdout.write("=" * 20)

        self.stdout.write(self.style.SUCCESS("Successfully imported MicroMasters data"))
