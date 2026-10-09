"""Tests for the check_nplusone fixture's zeal_allow marker"""

import pytest
from zeal import zeal_context

from courses.factories import CourseRunFactory
from courses.models import CourseRun

pytestmark = [pytest.mark.django_db]


@pytest.mark.zeal_allow("courses.CourseRun", "course")
def test_zeal_allow_ignores_only_the_named_n_plus_one():
    """A zeal_allow marker suppresses its own model and field, and no other."""
    CourseRunFactory.create_batch(2)

    with zeal_context():
        runs = list(CourseRun.objects.all())
        for run in runs:
            _ = run.course

        with pytest.raises(
            UserWarning, match=r"N\+1 detected on courses\.CourseRun\.products"
        ):
            [list(run.products.all()) for run in runs]
