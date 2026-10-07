"""Tests for the staff contract provisioning API's HTTP surface."""

from types import SimpleNamespace

import pytest
from django.urls import reverse
from rest_framework import status

from b2b.api import ensure_enrollment_codes_exist
from b2b.constants import (
    CONTRACT_MEMBERSHIP_CODE,
    CONTRACT_MEMBERSHIP_MANAGED,
    CONTRACT_SETUP_STATUS_COMPLETE,
    CONTRACT_SETUP_STATUS_FAILED,
    CONTRACT_SETUP_STATUS_IN_PROGRESS,
)
from b2b.contracts import add_contract_variant_set, add_courseware_to_contract
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from courses.factories import CourseFactory, CourseRunFactory
from openedx.constants import (
    COURSE_RUN_CLONE_STATUS_CLONED,
    COURSE_RUN_CLONE_STATUS_FAILED,
    COURSE_RUN_CLONE_STATUS_PENDING,
)
from openedx.models import CourseRunClone
from variants.factories import CourseSupportedVariantFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture(autouse=True)
def mocked_tasks(mocker):
    """Keep edX, code generation, sheets and email out of the requests."""

    mocker.patch("b2b.contracts.push_run_dates_to_edx")
    mocker.patch("b2b.tasks.queue_contract_sheet_update_post_save.delay")
    mocker.patch("b2b.tasks.queue_send_enrollment_code_assignment_email.delay")
    return SimpleNamespace(
        clone=mocker.patch("openedx.tasks.clone_courserun.delay"),
        code_check=mocker.patch("b2b.tasks.queue_enrollment_code_check.delay"),
    )


def _contracts_url(org_key):
    return reverse(
        "b2b:b2b-provisioning-organization-contract-list",
        kwargs={"parent_lookup_organization__org_key": org_key},
    )


def _contract_url(contract, suffix="detail"):
    return reverse(
        f"b2b:b2b-provisioning-organization-contract-{suffix}",
        kwargs={
            "parent_lookup_organization__org_key": contract.organization.org_key,
            "pk": contract.id,
        },
    )


def _source_course():
    """Create a course with a source run contract runs can be cloned from."""

    return CourseRunFactory.create(
        is_source_run=True, language="en", is_primary_language=True
    ).course


def test_contract_routes_require_staff(user_drf_client):
    """
    Plain authenticated users can't read either: the codes routes return
    redeemable enrollment codes.
    """

    contract = ContractPageFactory.create()

    assert (
        user_drf_client.get(_contracts_url(contract.organization.org_key)).status_code
        == status.HTTP_403_FORBIDDEN
    )
    assert (
        user_drf_client.get(_contract_url(contract, "codes")).status_code
        == status.HTTP_403_FORBIDDEN
    )
    assert (
        user_drf_client.post(
            _contracts_url(contract.organization.org_key),
            {"name": "x", "membership_type": CONTRACT_MEMBERSHIP_MANAGED},
            format="json",
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )


def test_create_contract(admin_drf_client, mocked_tasks):
    """A created contract has a default variant set and no codes yet."""

    organization = OrganizationPageFactory.create()

    response = admin_drf_client.post(
        _contracts_url(organization.org_key),
        {
            "name": "Spring cohort",
            "membership_type": CONTRACT_MEMBERSHIP_CODE,
            "max_learners": 20,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["organization"] == organization.id
    assert body["max_learners"] == 20
    assert body["programs"] == []
    contract = organization.contracts.get()
    assert contract.variant_options.filter(default_variant=True).exists()
    mocked_tasks.code_check.assert_not_called()


def test_create_contract_requires_membership_type(admin_drf_client):
    """membership_type has a model default, but creating a contract requires it."""

    organization = OrganizationPageFactory.create()

    response = admin_drf_client.post(
        _contracts_url(organization.org_key), {"name": "Spring cohort"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "membership_type" in response.json()["errors"]
    assert not organization.contracts.exists()


def test_create_contract_for_unknown_organization_is_a_404(admin_drf_client):
    """A mistyped org_key does not create an orphaned contract."""

    response = admin_drf_client.post(
        _contracts_url("NOSUCHORG"),
        {"name": "x", "membership_type": CONTRACT_MEMBERSHIP_MANAGED},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_contracts_are_scoped_to_their_organization(admin_drf_client):
    """Another organization's contract is invisible under this org_key."""

    contract = ContractPageFactory.create()
    other = ContractPageFactory.create()

    response = admin_drf_client.get(_contracts_url(contract.organization.org_key))

    assert [item["id"] for item in response.json()["results"]] == [contract.id]
    assert (
        admin_drf_client.get(
            reverse(
                "b2b:b2b-provisioning-organization-contract-detail",
                kwargs={
                    "parent_lookup_organization__org_key": contract.organization.org_key,
                    "pk": other.id,
                },
            )
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )


@pytest.mark.parametrize(
    ("membership_type", "queues_code_check"),
    [(CONTRACT_MEMBERSHIP_CODE, True), (CONTRACT_MEMBERSHIP_MANAGED, False)],
)
def test_patch_contract(
    admin_drf_client, mocked_tasks, membership_type, queues_code_check
):
    """An update reaches the codes of a contract that uses them."""

    contract = ContractPageFactory.create(membership_type=membership_type)

    response = admin_drf_client.patch(
        _contract_url(contract), {"max_learners": 50}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    contract.refresh_from_db()
    assert contract.max_learners == 50
    assert mocked_tasks.code_check.called is queues_code_check


def test_add_courseware_and_follow_setup(admin_drf_client, mocked_tasks):
    """
    Adding a course creates its run before returning, and setup status tracks
    the clone that follows.
    """

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED, enrollment_fixed_price=None
    )
    course = _source_course()

    response = admin_drf_client.post(
        _contract_url(contract, "courseware"),
        {"courseware_id": course.readable_id},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["runs_added"] == 1
    [run] = contract.get_course_runs()
    mocked_tasks.clone.assert_called_once()

    setup = admin_drf_client.get(_contract_url(contract, "setup-status")).json()
    assert setup["status"] == CONTRACT_SETUP_STATUS_IN_PROGRESS
    assert setup["runs"] == [
        {
            "courseware_id": run.courseware_id,
            "clone_status": COURSE_RUN_CLONE_STATUS_PENDING,
            "clone_attempts": 0,
            "clone_error": "",
        }
    ]
    [variant_set] = setup["variants"]
    assert variant_set["id"] == contract.default_variant_options.id
    assert variant_set["courses"] == [
        {
            "course_id": course.id,
            "readable_id": course.readable_id,
            "title": course.title,
            "has_source_run": True,
            "contract_run": run.courseware_id,
        }
    ]
    assert variant_set["unsupported_courses"] == []

    CourseRunClone.objects.filter(course_run=run).update(
        status=COURSE_RUN_CLONE_STATUS_CLONED
    )
    setup = admin_drf_client.get(_contract_url(contract, "setup-status")).json()
    assert setup["status"] == CONTRACT_SETUP_STATUS_COMPLETE


def test_add_unknown_courseware_is_a_404(admin_drf_client):
    """A readable ID that matches nothing is a 404."""

    contract = ContractPageFactory.create()

    response = admin_drf_client.post(
        _contract_url(contract, "courseware"),
        {"courseware_id": "course-v1:MITx+NOPE+1T2099"},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_add_course_without_source_run_is_a_400(admin_drf_client):
    """A course with nothing to clone from is reported, not a 500."""

    contract = ContractPageFactory.create()
    course = CourseFactory.create()

    response = admin_drf_client.post(
        _contract_url(contract, "courseware"),
        {"courseware_id": course.readable_id},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "source run" in response.json()["detail"]


def test_retry_setup_requeues_failed_clones(admin_drf_client, mocked_tasks):
    """A failed clone shows as failed, and retrying queues it again."""

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED, enrollment_fixed_price=None
    )
    add_courseware_to_contract(contract, _source_course())
    [run] = contract.get_course_runs()
    clone = CourseRunClone.objects.get(course_run=run)
    clone.status = COURSE_RUN_CLONE_STATUS_FAILED
    clone.save()
    mocked_tasks.clone.reset_mock()

    assert (
        admin_drf_client.get(_contract_url(contract, "setup-status")).json()["status"]
        == CONTRACT_SETUP_STATUS_FAILED
    )

    response = admin_drf_client.post(_contract_url(contract, "retry-setup"))

    assert response.json()["status"] == CONTRACT_SETUP_STATUS_IN_PROGRESS
    mocked_tasks.clone.assert_called_once_with(run.id, clone.source_courseware_id)
    clone.refresh_from_db()
    assert clone.status == COURSE_RUN_CLONE_STATUS_PENDING


def test_remove_courseware(admin_drf_client):
    """Removing a course reports each run and whether it was unlinked."""

    contract = ContractPageFactory.create()
    course = _source_course()
    add_courseware_to_contract(contract, course, skip_edx=True)
    [run] = contract.get_course_runs()

    response = admin_drf_client.post(
        _contract_url(contract, "remove-courseware"),
        {"courseware_id": course.readable_id},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [{"courseware_id": run.courseware_id, "unlinked": True}]
    assert not contract.get_course_runs().exists()


@pytest.fixture
def code_contract():
    """A seat-capped code contract with two codes for one run."""

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE, max_learners=2
    )
    add_courseware_to_contract(contract, _source_course(), skip_edx=True)
    ensure_enrollment_codes_exist(contract)
    return contract


def test_list_codes(admin_drf_client, code_contract):
    """Codes come back paginated."""

    response = admin_drf_client.get(_contract_url(code_contract, "codes"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["count"] == 2


def test_assign_codes(admin_drf_client, code_contract):
    """Assigning takes a free code per person and reports who got one."""

    response = admin_drf_client.post(
        _contract_url(code_contract, "assign-codes"),
        [{"email": "learner@example.com", "name": "A Learner"}],
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body["assigned"]) == 1
    assert body["errors"] == []
    assert code_contract.get_assignments().count() == 1


def test_expire_codes(admin_drf_client, code_contract):
    """Expiring takes the unused codes out of the contract."""

    response = admin_drf_client.post(_contract_url(code_contract, "expire-codes"))

    assert response.status_code == status.HTTP_200_OK
    assert [item["deleted"] for item in response.json()] == [True, True]
    assert not code_contract.get_discounts().exists()


def _variant_url(contract, variant):
    return reverse(
        "b2b:b2b-provisioning-organization-contract-variant-detail",
        kwargs={
            "parent_lookup_organization__org_key": contract.organization.org_key,
            "pk": contract.id,
            "variant_id": variant.id,
        },
    )


def test_variant_routes_require_staff(user_drf_client):
    """The variant routes are staff-only like the rest of the contract routes."""

    contract = ContractPageFactory.create()
    url = _contract_url(contract, "variants")

    assert user_drf_client.get(url).status_code == status.HTTP_403_FORBIDDEN
    assert (
        user_drf_client.post(url, {"language": "fr"}, format="json").status_code
        == status.HTTP_403_FORBIDDEN
    )
    assert (
        user_drf_client.patch(
            _variant_url(contract, contract.default_variant_options),
            {"active": True},
            format="json",
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )


def test_list_variant_sets(admin_drf_client):
    """The default set comes first, with the contract's courses it matches."""

    contract = ContractPageFactory.create()
    course = _source_course()
    add_courseware_to_contract(contract, course)
    [contract_run] = contract.get_course_runs()
    french = add_contract_variant_set(contract, language="fr")
    CourseSupportedVariantFactory.create(
        variant_object=course, language="fr", variant_length="", variant_industry=""
    )

    response = admin_drf_client.get(_contract_url(contract, "variants"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [
        {
            "id": contract.default_variant_options.id,
            "language": "en",
            "variant_length": "",
            "variant_industry": "",
            "default_variant": True,
            "active": True,
            "b2b_only": False,
            "courses": [
                {
                    "course_id": course.id,
                    "readable_id": course.readable_id,
                    "title": course.title,
                    "has_source_run": True,
                    "contract_run": contract_run.courseware_id,
                }
            ],
            "unsupported_courses": [],
        },
        {
            "id": french.id,
            "language": "fr",
            "variant_length": "",
            "variant_industry": "",
            "default_variant": False,
            "active": True,
            "b2b_only": False,
            "courses": [
                {
                    "course_id": course.id,
                    "readable_id": course.readable_id,
                    "title": course.title,
                    "has_source_run": False,
                    "contract_run": None,
                }
            ],
            "unsupported_courses": [],
        },
    ]


def test_add_variant_set(admin_drf_client, admin_user):
    """A new set is never the default, and the add is audited."""

    contract = ContractPageFactory.create()

    response = admin_drf_client.post(
        _contract_url(contract, "variants"),
        {"language": "fr", "variant_industry": "", "b2b_only": True},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["language"] == "fr"
    assert body["default_variant"] is False
    assert body["b2b_only"] is True
    assert body["courses"] == []
    audit = contract.organization.provisioning_audits.get()
    assert audit.acting_user == admin_user
    assert audit.data_after["variant_id"] == body["id"]


@pytest.mark.parametrize(
    "payload",
    [{}, {"language": ""}, {"language": "xx-not-a-language"}, {"language": "fr"}],
    ids=["missing", "blank", "invalid", "duplicate"],
)
def test_add_variant_set_rejected(admin_drf_client, payload):
    """Bad and duplicate sets are a 400, not an IntegrityError or 500."""

    contract = ContractPageFactory.create()
    admin_drf_client.post(
        _contract_url(contract, "variants"), {"language": "fr"}, format="json"
    )

    response = admin_drf_client.post(
        _contract_url(contract, "variants"), payload, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert contract.variant_options.count() == 2


def test_update_variant_set(admin_drf_client):
    """A non-default set can be turned off and back on, and made B2B-only."""

    contract = ContractPageFactory.create()
    variant = admin_drf_client.post(
        _contract_url(contract, "variants"), {"language": "fr"}, format="json"
    ).json()
    url = _variant_url(contract, contract.variant_options.get(id=variant["id"]))

    response = admin_drf_client.patch(
        url, {"active": False, "b2b_only": True}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["active"] is False
    assert response.json()["b2b_only"] is True
    assert (
        admin_drf_client.patch(url, {"active": True}, format="json").json()["active"]
        is True
    )


def test_update_default_variant_set_rejected(admin_drf_client):
    """The default set can't be turned off."""

    contract = ContractPageFactory.create()

    response = admin_drf_client.patch(
        _variant_url(contract, contract.default_variant_options),
        {"active": False},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "default variant set" in response.json()["detail"]
    assert contract.default_variant_options.active is True


def test_update_variant_set_of_another_contract(admin_drf_client):
    """A variant set ID from another contract is a 404."""

    contract = ContractPageFactory.create()
    other = ContractPageFactory.create(organization=contract.organization)

    response = admin_drf_client.patch(
        _variant_url(contract, other.default_variant_options),
        {"active": False},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
