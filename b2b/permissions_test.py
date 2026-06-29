"""Tests for b2b permissions."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from unittest.mock import MagicMock

from b2b.factories import OrganizationPageFactory, UserOrganizationFactory
from b2b.permissions import IsOrganizationManager
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def permission():
    return IsOrganizationManager()


@pytest.fixture
def organization():
    return OrganizationPageFactory.create()


def make_view(org_id):
    view = MagicMock()
    view.kwargs = {"parent_lookup_organization": org_id}
    return view


class TestIsOrganizationManagerHasPermission:
    def test_unauthenticated_user_denied(self, rf, permission, organization):
        request = rf.get("/")
        request.user = AnonymousUser()
        view = make_view(organization.id)
        assert permission.has_permission(request, view) is False

    def test_superuser_always_allowed(self, rf, permission, organization):
        user = UserFactory.create(is_superuser=True)
        request = rf.get("/")
        request.user = user
        view = make_view(organization.id)
        assert permission.has_permission(request, view) is True

    def test_manager_of_org_allowed(self, rf, permission, organization):
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        assert permission.has_permission(request, view) is True

    def test_non_manager_member_denied(self, rf, permission, organization):
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=False
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        assert permission.has_permission(request, view) is False

    def test_manager_of_different_org_denied(self, rf, permission, organization):
        other_org = OrganizationPageFactory.create()
        user_org = UserOrganizationFactory.create(
            organization=other_org, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        assert permission.has_permission(request, view) is False

    def test_missing_org_id_in_kwargs_denied(self, rf, permission):
        user = UserFactory.create()
        request = rf.get("/")
        request.user = user
        view = MagicMock()
        view.kwargs = {}
        assert permission.has_permission(request, view) is False


class TestIsOrganizationManagerHasObjectPermission:
    def test_superuser_always_allowed(self, rf, permission, organization):
        user = UserFactory.create(is_superuser=True)
        request = rf.get("/")
        request.user = user
        view = make_view(organization.id)
        obj = MagicMock(spec=[])
        assert permission.has_object_permission(request, view, obj) is True

    def test_manager_with_organization_id_attr_matching(
        self, rf, permission, organization
    ):
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        obj = MagicMock()
        obj.organization_id = organization.id
        assert permission.has_object_permission(request, view, obj) is True

    def test_manager_with_organization_id_attr_mismatched(
        self, rf, permission, organization
    ):
        other_org = OrganizationPageFactory.create()
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        obj = MagicMock()
        obj.organization_id = other_org.id
        assert permission.has_object_permission(request, view, obj) is False

    def test_manager_with_organization_attr_matching(
        self, rf, permission, organization
    ):
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        obj = MagicMock(spec=["organization"])
        obj.organization = MagicMock()
        obj.organization.id = organization.id
        assert permission.has_object_permission(request, view, obj) is True

    def test_manager_with_organization_attr_mismatched(
        self, rf, permission, organization
    ):
        other_org = OrganizationPageFactory.create()
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        obj = MagicMock(spec=["organization"])
        obj.organization = MagicMock()
        obj.organization.id = other_org.id
        assert permission.has_object_permission(request, view, obj) is False

    def test_manager_with_b2b_contract_attr_matching(
        self, rf, permission, organization
    ):
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        obj = MagicMock(spec=["b2b_contract"])
        obj.b2b_contract = MagicMock()
        obj.b2b_contract.organization_id = organization.id
        assert permission.has_object_permission(request, view, obj) is True

    def test_manager_with_b2b_contract_attr_mismatched(
        self, rf, permission, organization
    ):
        other_org = OrganizationPageFactory.create()
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        obj = MagicMock(spec=["b2b_contract"])
        obj.b2b_contract = MagicMock()
        obj.b2b_contract.organization_id = other_org.id
        assert permission.has_object_permission(request, view, obj) is False

    def test_manager_with_run_b2b_contract_attr_matching(
        self, rf, permission, organization
    ):
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        obj = MagicMock(spec=["run"])
        obj.run = MagicMock(spec=["b2b_contract"])
        obj.run.b2b_contract = MagicMock()
        obj.run.b2b_contract.organization_id = organization.id
        assert permission.has_object_permission(request, view, obj) is True

    def test_manager_with_run_b2b_contract_attr_mismatched(
        self, rf, permission, organization
    ):
        other_org = OrganizationPageFactory.create()
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        obj = MagicMock(spec=["run"])
        obj.run = MagicMock(spec=["b2b_contract"])
        obj.run.b2b_contract = MagicMock()
        obj.run.b2b_contract.organization_id = other_org.id
        assert permission.has_object_permission(request, view, obj) is False
