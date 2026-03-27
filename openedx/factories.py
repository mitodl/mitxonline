"""Courseware factories"""

from datetime import timedelta
from zoneinfo import ZoneInfo

import faker
from edx_api.course_detail.models import CourseMode
from factory import Factory, Faker, LazyAttribute, SelfAttribute, SubFactory, Trait
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText
from mitol.common.utils import now_in_utc

from openedx.constants import PLATFORM_EDX
from openedx.models import OpenEdxApiAuth, OpenEdxUser

FAKE = faker.Factory.create()


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
    access_token_expires_on = Faker(
        "future_datetime", end_date="+10h", tzinfo=ZoneInfo("UTC")
    )

    class Meta:
        model = OpenEdxApiAuth

    class Params:
        expired = Trait(
            access_token_expires_on=LazyAttribute(
                lambda _: now_in_utc() - timedelta(days=1)
            )
        )


class CourseModeProxy:
    """Proxy for CourseMode, which doesn't instantiate in a way that works with Factory"""

    coursemode = None

    def __init__(self, mode_slug, mode_display_name, course_id):
        """Init a CourseMode and return that instead"""

        self.coursemode = CourseMode(
            {
                "mode_slug": mode_slug,
                "mode_disply_name": mode_display_name,
                "course_id": course_id,
            }
        )


class CourseModeFactory(Factory):
    """Factory for edX Course Modes"""

    mode_slug = FAKE.slug()
    mode_display_name = FAKE.catch_phrase()
    course_id = FAKE.slug()

    class Meta:
        model = CourseModeProxy

    @classmethod
    def create(cls, *args, **kwargs):
        """Generate, but return the proxy's CourseMode."""

        proxy_obj = super().create(*args, **kwargs)
        return proxy_obj.coursemode
