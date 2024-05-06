import pytest

from courses.factories import CourseFactory
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.models import FlexiblePrice
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


def test_submission_status():
    """
    Tests the is_approved and is_denied methods.
    """

    for status in FlexiblePriceStatus.ALL_STATUSES:
        user = UserFactory.create()
        course = CourseFactory.create()
        submission = FlexiblePrice.objects.create(
            user=user, status=status, courseware_object=course
        )

        if (
            status == FlexiblePriceStatus.APPROVED  # noqa: PLR1714
            or status == FlexiblePriceStatus.AUTO_APPROVED
        ):
            assert submission.is_approved()
        elif status == FlexiblePriceStatus.DENIED:
            assert submission.is_denied()
        elif status == FlexiblePriceStatus.RESET:
            assert submission.is_reset()
        else:
            assert not submission.is_approved() and not submission.is_denied()  # noqa: PT018
