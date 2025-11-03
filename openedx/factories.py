"""Courseware factories"""

from datetime import timedelta
from urllib.parse import quote

import pytz
from django.conf import settings
from edx_api.course_detail.models import CourseDetail
from factory import Faker, LazyAttribute, SelfAttribute, SubFactory, Trait
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText
from mitol.common.utils import now_in_utc

from openedx.constants import PLATFORM_EDX
from openedx.models import OpenEdxApiAuth, OpenEdxUser


class OpenEdxUserFactory(DjangoModelFactory):
    """Factory for OpenEdxUser"""

    user = SubFactory("users.factories.UserFactory", no_openedx_user=True)
    platform = PLATFORM_EDX
    has_been_synced = True
    edx_username = FuzzyText()
    desired_edx_username = SelfAttribute("edx_username")

    class Meta:
        model = OpenEdxUser


class OpenEdxApiAuthFactory(DjangoModelFactory):
    """Factory for OpenEdxApiAuth"""

    user = SubFactory("users.factories.UserFactory", no_openedx_api_auth=True)
    refresh_token = Faker("pystr", max_chars=30)
    access_token = Faker("pystr", max_chars=30)
    access_token_expires_on = Faker("future_datetime", end_date="+10h", tzinfo=pytz.utc)

    class Meta:
        model = OpenEdxApiAuth

    class Params:
        expired = Trait(
            access_token_expires_on=LazyAttribute(
                lambda _: now_in_utc() - timedelta(days=1)
            )
        )


class MockOpenEdxCourseDetailClient:
    """Mock detail client"""

    courses = {}

    def _mock_course_detail(self, course_id: str):
        """Generate a bunch of mock data for the course"""

        if course_id not in self.courses:
            fake_date = Faker("date_time", tzinfo=pytz.timezone(settings.TIME_ZONE))

            detail = {
                "blocks_url": f"http://192.168.33.10:8000/api/courses/v1/blocks/?course_id={quote(course_id)}",
                "effort": "7 hours",
                "end": str(fake_date + timedelta(days=90)),
                "enrollment_start": str(fake_date - timedelta(days=45)),
                "enrollment_end": None,
                "id": course_id,
                "media": {
                    "course_image": {
                        "uri": "/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg"
                    },
                    "course_video": {
                        "uri": None
                    }
                },
                "name": Faker("words", nb=3),
                "number": "DemoX",
                "org": "edX",
                "short_description": "",
                "start": str(fake_date - timedelta(days=30)),
                "start_display": (fake_date - timedelta(days=30)).strftime("%B %w, %Y"),
                "start_type": "timestamp",
                "course_id": course_id,
                "overview": "<h2>About This Course</h2>\n   <p>Include your long course description here. The long course description should contain 150-400 words.</p>\n",
                "pacing": "self"
            }

            self.courses[course_id] = CourseDetail(detail)

        return self.courses[course_id]

    def get_detail(self, course_id: str, username: str):
        """Return detail about an edX course."""

        return self._mock_course_detail(course_id)
