"""Factory for Users"""
from factory import (
    Faker,
    RelatedFactory,
    SubFactory,
    Trait,
    fuzzy,
)
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText
from social_django.models import UserSocialAuth

from users.models import GENDER_CHOICES, LegalAddress, Profile, User


class UserFactory(DjangoModelFactory):
    """Factory for Users"""

    username = FuzzyText()
    email = FuzzyText(suffix="@example.com")
    name = Faker("name")
    password = FuzzyText(length=8)
    is_superuser = False
    is_staff = False

    is_active = True

    legal_address = RelatedFactory("users.factories.LegalAddressFactory", "user")
    profile = RelatedFactory("users.factories.ProfileFactory", "user")

    class Meta:
        model = User


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


class ProfileFactory(DjangoModelFactory):
    """Factory for Profile"""

    user = SubFactory("users.factories.UserFactory")

    class Meta:
        model = Profile
