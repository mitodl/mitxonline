"""Tests for user models"""

# pylint: disable=too-many-arguments, redefined-outer-name
import random

import factory
import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction

from b2b.factories import ContractPageFactory, OrganizationPageFactory
from cms.constants import CMS_EDITORS_GROUP_NAME
from courses.factories import CourseRunEnrollmentFactory, CourseRunFactory
from openedx.factories import OpenEdxApiAuthFactory, OpenEdxUserFactory
from openedx.models import OpenEdxUser
from users.factories import UserFactory
from users.models import (
    HIGHEST_EDUCATION_CHOICES,
    OPENEDX_HIGHEST_EDUCATION_MAPPINGS,
    LegalAddress,
    User,
    UserOrganization,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def mocked_b2b_org_attach(mocker):
    """Mock the org attachment call."""

    return mocker.patch("b2b.api.add_user_org_membership", return_value=True)


@pytest.mark.parametrize(
    "create_func,exp_staff,exp_superuser,exp_is_active",  # noqa: PT006
    [
        [User.objects.create_user, False, False, True],  # noqa: PT007
        [User.objects.create_superuser, True, True, True],  # noqa: PT007
    ],
)
@pytest.mark.parametrize("password", [None, "pass"])
def test_create_user(create_func, exp_staff, exp_superuser, exp_is_active, password):  # pylint: disable=too-many-arguments
    """Test creating a user"""
    username = "user1"
    email = "uSer@EXAMPLE.com"
    name = "Jane Doe"
    with transaction.atomic():
        user = create_func(username, email=email, name=name, password=password)

    assert user.username == username
    assert user.email == "uSer@example.com"
    assert user.name == name
    assert user.get_full_name() == name
    assert user.is_staff is exp_staff
    assert user.is_superuser is exp_superuser
    assert user.is_active is exp_is_active
    assert user.edx_username == username
    if password is not None:
        assert user.check_password(password)

    assert LegalAddress.objects.filter(user=user).exists()
    assert OpenEdxUser.objects.filter(user=user, edx_username=username).exists()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"is_staff": False},
        {"is_superuser": False},
        {"is_staff": False, "is_superuser": False},
    ],
)
def test_create_superuser_error(kwargs):
    """Test creating a user"""
    with pytest.raises(ValueError):  # noqa: PT011
        User.objects.create_superuser(
            username=None,
            email="uSer@EXAMPLE.com",
            name="Jane Doe",
            password="abc",  # noqa: S106
            **kwargs,
        )


@pytest.mark.parametrize(
    "field, value, is_valid",  # noqa: PT006
    [
        ["country", "US", True],  # noqa: PT007
        ["country", "United States", False],  # noqa: PT007
    ],
)
def test_legal_address_validation(field, value, is_valid):
    """Verify legal address validation"""
    address = LegalAddress()

    setattr(address, field, value)

    with pytest.raises(ValidationError) as exc:
        address.clean_fields()

    if is_valid:
        assert field not in exc.value.error_dict
    else:
        assert field in exc.value.error_dict


@pytest.mark.django_db
def test_faulty_user_qset():
    """User.faulty_openedx_users should return a User queryset that contains incorrectly configured active Users"""
    users = UserFactory.create_batch(5, no_openedx_user=True, no_openedx_api_auth=True)
    # An inactive user should not be returned even if they lack auth and openedx user records
    UserFactory.create(is_active=False, no_openedx_user=True, no_openedx_api_auth=True)
    good_users = users[0:2]
    expected_faulty_users = users[2:]
    # Create OpenEdxUser for one of the faulty users
    OpenEdxUserFactory.create(user=expected_faulty_users[0], has_been_synced=False)
    # Create OpenEdxApiAuth for the same faulty user
    OpenEdxApiAuthFactory.create(user=expected_faulty_users[0])
    OpenEdxApiAuthFactory.create_batch(
        3,
        user=factory.Iterator(good_users + [users[3]]),  # noqa: RUF005
    )
    OpenEdxUserFactory.create_batch(3, user=factory.Iterator(good_users + [users[4]]))  # noqa: RUF005

    assert set(User.faulty_openedx_users.values_list("id", flat=True)) == {
        user.id for user in expected_faulty_users
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_staff, is_superuser, has_editor_group, exp_is_editor",  # noqa: PT006
    [
        [True, True, True, True],  # noqa: PT007
        [True, False, False, True],  # noqa: PT007
        [False, True, False, True],  # noqa: PT007
        [False, False, True, True],  # noqa: PT007
        [False, False, False, False],  # noqa: PT007
    ],
)
def test_user_is_editor(is_staff, is_superuser, has_editor_group, exp_is_editor):
    """User.is_editor should return True if a user is staff, superuser, or belongs to the 'editor' group"""
    user = UserFactory.create(is_staff=is_staff, is_superuser=is_superuser)
    if has_editor_group:
        user.groups.add(Group.objects.get(name=CMS_EDITORS_GROUP_NAME))
        user.save()
    assert user.is_editor is exp_is_editor


def test_legal_address_us_state():
    """
    Tests to make sure the us_state property is working properly.

    This should be:
    - the state code alone if the user's country is US and the state is specified
    - None if the state is not specified or if the country is not US
    """

    user = UserFactory.create()
    legal_address = user.legal_address

    legal_address.country = "US"
    legal_address.state = "US-MA"
    legal_address.save()

    assert legal_address.us_state == "MA"

    legal_address.country = "US"
    legal_address.state = None
    legal_address.save()

    assert legal_address.us_state == None  # noqa: E711

    legal_address.country = "JP"
    legal_address.save()

    assert legal_address.us_state == None  # noqa: E711


def test_user_profile_edx_education():
    user = UserFactory.create()

    user.user_profile.highest_education = HIGHEST_EDUCATION_CHOICES[
        random.randrange(1, len(HIGHEST_EDUCATION_CHOICES))  # noqa: S311
    ][0]
    user.save()

    test_openedx_flag = [  # noqa: RUF015
        item[1]
        for item in OPENEDX_HIGHEST_EDUCATION_MAPPINGS
        if item[0] == user.user_profile.highest_education
    ][0]

    assert user.user_profile.highest_education is not None
    assert user.user_profile.level_of_education is not None
    assert user.user_profile.level_of_education == test_openedx_flag


@pytest.mark.parametrize("should_exist", [True, False])
def test_user_profile_edx_properties(should_exist):
    user = UserFactory.create()

    user.legal_address.country = "US"

    if should_exist:
        user.user_profile.gender = "f"
        user.legal_address.state = "US-MA"
    else:
        user.user_profile.gender = "nb"
        user.user_profile.state = "US-AS"

    assert (
        user.user_profile.edx_gender == "f"
        if should_exist
        else user.user_profile.edx_gender == "o"
    )
    assert (
        user.legal_address.edx_us_state == "MA"
        if should_exist
        else user.legal_address.edx_us_state is None
    )


def test_user_add_b2b_org(mocked_b2b_org_attach):
    """Ensure adding a user to an organization works as expected."""

    orgs = OrganizationPageFactory.create_batch(2)
    user = UserFactory.create()

    # New-style ones
    contract_auto = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="auto",
        title="Contract Auto",
        name="Contract Auto",
    )
    contract_managed = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="managed",
        title="Contract Managed",
        name="Contract Managed",
    )
    contract_code = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="code",
        title="Contract Enrollment Code",
        name="Contract Enrollment Code",
    )
    # Legacy ones - these will migrate to "managed" and "code"
    contract_sso = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="sso",
        title="Contract SSO",
        name="Contract SSO",
    )
    contract_non_sso = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="non-sso",
        title="Contract NonSSO",
        name="Contract NonSSO",
    )

    UserOrganization.process_add_membership(user, orgs[0])

    # We should now be in the SSO, auto, and managed contracts
    # but not the other two.

    user.refresh_from_db()
    assert user.b2b_contracts.count() == 3
    assert user.b2b_organizations.filter(organization=orgs[0]).exists()
    assert (
        user.b2b_contracts.filter(
            pk__in=[
                contract_auto.id,
                contract_sso.id,
                contract_managed.id,
            ]
        ).count()
        == 3
    )
    assert (
        user.b2b_contracts.filter(
            pk__in=[
                contract_code.id,
                contract_non_sso.id,
            ]
        ).count()
        == 0
    )


def test_user_remove_b2b_org(mocked_b2b_org_attach):
    """Ensure removing a user from an org also clears the appropriate contracts."""

    orgs = OrganizationPageFactory.create_batch(2)
    user = UserFactory.create()

    # New-style ones
    contract_auto = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="auto",
        title="Contract Auto",
        name="Contract Auto",
    )
    contract_managed = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="managed",
        title="Contract Managed",
        name="Contract Managed",
    )
    contract_code = ContractPageFactory.create(
        organization=orgs[1],
        membership_type="code",
        title="Contract Enrollment Code",
        name="Contract Enrollment Code",
    )
    # Legacy ones - these will migrate to "managed" and "code"
    contract_sso = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="sso",
        title="Contract SSO",
        name="Contract SSO",
    )
    contract_non_sso = ContractPageFactory.create(
        organization=orgs[1],
        membership_type="non-sso",
        title="Contract NonSSO",
        name="Contract NonSSO",
    )

    managed_ids = [
        contract_auto.id,
        contract_managed.id,
        contract_sso.id,
    ]
    unmanaged_ids = [
        contract_code.id,
        contract_non_sso.id,
    ]

    UserOrganization.process_add_membership(user, orgs[0])
    UserOrganization.process_add_membership(user, orgs[1])

    user.b2b_contracts.add(contract_code)
    user.b2b_contracts.add(contract_non_sso)
    user.save()

    user.refresh_from_db()

    assert user.b2b_contracts.count() == 5

    UserOrganization.process_remove_membership(user, orgs[1])

    assert user.b2b_contracts.filter(id__in=managed_ids).count() == 3
    assert user.b2b_contracts.filter(id__in=unmanaged_ids).count() == 0

    UserOrganization.process_remove_membership(user, orgs[0])

    # we should have no contracts now since we're no longer in any orgs

    assert user.b2b_contracts.count() == 0


def test_b2b_contract_removal_keeps_enrollments(mocked_b2b_org_attach):
    """Ensure that removing a user from a B2B contract leaves their enrollments alone."""

    org = OrganizationPageFactory.create()
    user = UserFactory.create()

    contract_auto = ContractPageFactory.create(
        organization=org,
        membership_type="auto",
        title="Contract Auto",
        name="Contract Auto",
    )

    courserun = CourseRunFactory.create(b2b_contract=contract_auto)

    UserOrganization.process_add_membership(user, org)

    CourseRunEnrollmentFactory(
        user=user,
        run=courserun,
    )

    user.refresh_from_db()

    assert courserun.enrollments.filter(user=user).count() == 1

    UserOrganization.process_remove_membership(user, org)

    assert courserun.enrollments.filter(user=user).count() == 1


def test_b2b_org_attach_calls_keycloak(mocked_b2b_org_attach):
    """Test that attaching a user to an org calls Keycloak successfully."""

    org = OrganizationPageFactory.create()
    user = UserFactory.create()

    UserOrganization.process_add_membership(user, org)

    mocked_b2b_org_attach.assert_called()
