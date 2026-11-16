"""Throwaway probe: report the CI test database's collation. Fails on purpose."""

import pytest
from django.db import connection

pytestmark = [pytest.mark.django_db]


def test_probe_ci_database_collation():
    """Fail with the database collation and how it orders the two CI ids."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_database(), datcollate, datctype, version() "
            "FROM pg_database WHERE datname = current_database()"
        )
        info = cursor.fetchone()
        cursor.execute(
            "SELECT x FROM (VALUES ('course-v1:PyT+CRa-my-affect+R550'), "
            "('course-v1:PyT+CRadd-life-day-put+R551')) AS t(x) ORDER BY x"
        )
        first = cursor.fetchone()[0]
    pytest.fail(
        f"PROBE db={info[0]} collate={info[1]} ctype={info[2]} first={first} | {info[3]}"
    )
