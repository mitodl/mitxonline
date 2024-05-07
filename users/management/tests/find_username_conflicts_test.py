"""Tests the username conflict finder."""

from io import StringIO

import pytest
from django.core.management import call_command

from users.factories import UserFactory


@pytest.mark.parametrize("with_accents", [True, False])
@pytest.mark.django_db
def test_find_username_conflicts(with_accents):
    users = UserFactory.create_batch(2)

    if with_accents:
        users[0].username = "aeiou"
        users[0].save()

        users[1].username = "aéîöü"
        users[1].save()

    output = StringIO()
    call_command("find_username_conflicts", stdout=output)

    if with_accents:
        assert "has conflicts" in output.getvalue()
    else:
        assert "has conflicts" not in output.getvalue()
