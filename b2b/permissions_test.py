"""Tests for b2b permissions."""

from unittest.mock import MagicMock

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from b2b.factories import (
    ContractPageFactory,
    OrganizationPageFactory,
    UserOrganizationFactory,
)
from b2b.permissions import IsOrganizationManager
from courses.factories import CourseRunFactory
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

    @pytest.mark.parametrize("matching", [True, False])
    def test_manager_with_course_run(self, rf, permission, organization, matching):
        """Course runs are checked against all of their contracts."""
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        run = CourseRunFactory.create()
        run.b2b_contracts.add(ContractPageFactory.create())
        if matching:
            run.b2b_contracts.add(ContractPageFactory.create(organization=organization))
        assert permission.has_object_permission(request, view, run) is matching

    @pytest.mark.parametrize("matching", [True, False])
    def test_manager_with_run_b2b_contracts(
        self, rf, permission, organization, matching
    ):
        """Objects with a run are checked against the run's contracts."""
        user_org = UserOrganizationFactory.create(
            organization=organization, is_manager=True
        )
        request = rf.get("/")
        request.user = user_org.user
        view = make_view(organization.id)
        obj = MagicMock(spec=["run"])
        obj.run = CourseRunFactory.create()
        obj.run.b2b_contracts.add(
            ContractPageFactory.create(
                organization=organization
                if matching
                else OrganizationPageFactory.create()
            )
        )
        assert permission.has_object_permission(request, view, obj) is matching
