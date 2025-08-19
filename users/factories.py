"""Factory for Users"""

import random
from datetime import datetime

from factory import Faker, RelatedFactory, SelfAttribute, SubFactory, Trait
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText
from social_django.models import UserSocialAuth

from users.models import GENDER_CHOICES, LegalAddress, User, UserProfile


class UserFactory(DjangoModelFactory):
    """Factory for Users"""

    username = SelfAttribute("email")
    email = FuzzyText(suffix="@example.com")
    name = Faker("name")
    password = FuzzyText(length=8)
    global_id = Faker("uuid4")
    is_superuser = False
    is_staff = False

    is_active = True

    legal_address = RelatedFactory("users.factories.LegalAddressFactory", "user")
    user_profile = RelatedFactory(
        "users.factories.UserProfileFactory",
        "user",
    )
    openedx_user = RelatedFactory(
        "openedx.factories.OpenEdxUserFactory",
        "user",
    )
    openedx_api_auth = RelatedFactory(
        "openedx.factories.OpenEdxApiAuthFactory",
        "user",
    )

    class Meta:
        model = User

    class Params:
        no_openedx_user = Trait(openedx_user=None)
        no_openedx_api_auth = Trait(openedx_api_auth=None)

        legacy_username = Trait(username=FuzzyText())


class UserSocialAuthFactory(DjangoModelFactory):
    """Factory for UserSocialAuth"""

    provider = FuzzyText()
    user = SubFactory("users.factories.UserFactory")
    uid = FuzzyText()

    class Meta:
        model = UserSocialAuth


class LegalAddressFactory(DjangoModelFactory):
    """Factory for LegalAddress"""

    user = SubFactory("users.factories.UserFactory")

    first_name = Faker("first_name")
    last_name = Faker("last_name")
    country = Faker("country_code", representation="alpha-2")

    class Meta:
        model = LegalAddress


class UserProfileFactory(DjangoModelFactory):
    """Factory for Profile"""

    user = SubFactory("users.factories.UserFactory")

    year_of_birth = datetime.now().year - random.randint(1, 100)  # noqa: S311, DTZ005
    gender = GENDER_CHOICES[random.randint(0, len(GENDER_CHOICES) - 1)][0]  # noqa: S311

    class Meta:
        model = UserProfile
