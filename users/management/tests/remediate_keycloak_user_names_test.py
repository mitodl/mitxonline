"""Tests for remediate_keycloak_user_names management command"""

import json

import pytest

from b2b.keycloak_admin_dataclasses import UserRepresentation
from users.adapters import LearnUserAdapter
from users.factories import UserFactory
from users.management.commands import remediate_keycloak_user_names

COMMAND = remediate_keycloak_user_names.Command()


def _mock_client(mocker, pages):
    """pages: list of lists of UserRepresentation, terminated by an empty list"""
    client = mocker.Mock()
    client.list.side_effect = [*pages, []]
    return client


def _run(tmp_path, **options):
    """Run the command and return its parsed JSON report - reading the report
    file, rather than scraping stdout, avoids Command()'s stdout reference
    being grabbed at module-import time (before pytest's capture fixtures are
    active for the current test).
    """
    report_path = tmp_path / "report.json"
    COMMAND.handle(report_path=str(report_path), **options)
    return json.loads(report_path.read_text())


@pytest.fixture(autouse=True)
def mock_bootstrap(mocker):
    """Every test needs bootstrap_client mocked before it can set a return value."""
    return mocker.patch(
        "users.management.commands.remediate_keycloak_user_names.bootstrap_client"
    )


@pytest.mark.django_db
def test_mitxonline_users_lookup_query_count_is_flat(django_assert_max_num_queries):
    """_mitxonline_users_by_scim_id() plus constructing a LearnUserAdapter per
    user (as handle() does) must not issue extra queries per user - the fixed
    query count covers select_related(legal_address, user_profile) plus one
    bulk prefetch for openedx_users, regardless of how many users there are
    """
    for i in range(5):
        user = UserFactory.create(scim_external_id=f"kc-{i}")
        user.legal_address.first_name = "Joe"
        user.legal_address.last_name = "Smith"
        user.legal_address.save()

    with django_assert_max_num_queries(3):
        by_id = COMMAND._mitxonline_users_by_scim_id()  # noqa: SLF001
        for user in by_id.values():
            LearnUserAdapter(user)._resolve_name()  # noqa: SLF001


@pytest.mark.django_db
def test_dry_run_reports_without_patching(mocker, tmp_path):
    """A mismatched user is reported as would-patch; client.save is never called"""
    user = UserFactory.create(name="Joe Smith", scim_external_id="kc-1")
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    kc_user = UserRepresentation(id="kc-1", firstName="", lastName="")
    client = _mock_client(mocker, [[kc_user]])
    mock_bootstrap = remediate_keycloak_user_names.bootstrap_client
    mock_bootstrap.return_value = client

    report = _run(tmp_path, apply=False, limit=None)

    client.save.assert_not_called()
    assert [row["user_id"] for row in report["would_patch"]] == [user.id]


@pytest.mark.django_db
def test_apply_patches_and_verifies(mocker):
    """--apply calls client.save with the resolved name and fullName, then
    re-fetches to verify
    """
    user = UserFactory.create(name="Joe Smith", scim_external_id="kc-1")
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    kc_user = UserRepresentation(id="kc-1", firstName="", lastName="")
    client = _mock_client(mocker, [[kc_user]])
    client.retrieve.return_value = UserRepresentation(
        id="kc-1",
        firstName="Joe",
        lastName="Smith",
        attributes={"fullName": ["Joe Smith"]},
    )
    remediate_keycloak_user_names.bootstrap_client.return_value = client

    COMMAND.handle(apply=True, limit=None, report_path=None)

    client.save.assert_called_once_with(
        "users/kc-1",
        {
            "first_name": "Joe",
            "last_name": "Smith",
            "attributes": {"fullName": ["Joe Smith"]},
        },
    )
    client.retrieve.assert_called_once()


@pytest.mark.django_db
def test_up_to_date_user_is_skipped(mocker):
    """A user whose Keycloak record already matches - split name and
    fullName both - isn't touched
    """
    user = UserFactory.create(name="Joe Smith", scim_external_id="kc-1")
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    kc_user = UserRepresentation(
        id="kc-1",
        firstName="Joe",
        lastName="Smith",
        attributes={"fullName": ["Joe Smith"]},
    )
    client = _mock_client(mocker, [[kc_user]])
    remediate_keycloak_user_names.bootstrap_client.return_value = client

    COMMAND.handle(apply=True, limit=None, report_path=None)

    client.save.assert_not_called()


@pytest.mark.django_db
def test_single_name_user_with_null_keycloak_field_is_up_to_date(mocker):
    """A mononym user (resolved family_name == "") whose Keycloak record has
    lastName=None, not "", must still be treated as up to date once fullName
    also matches - None and "" both mean "no last name", and Keycloak may
    return either representation
    """
    user = UserFactory.create(name="Madonna", scim_external_id="kc-1")
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    kc_user = UserRepresentation(
        id="kc-1",
        firstName="Madonna",
        lastName=None,
        attributes={"fullName": ["Madonna"]},
    )
    client = _mock_client(mocker, [[kc_user]])
    remediate_keycloak_user_names.bootstrap_client.return_value = client

    COMMAND.handle(apply=True, limit=None, report_path=None)

    client.save.assert_not_called()


@pytest.mark.django_db
def test_no_legal_address_split_only_patches_full_name(mocker):
    """A user with no legal_address first/last (the common edxorg-migration
    case) only gets the fullName attribute patched - Keycloak's existing
    firstName/lastName are left alone rather than guessed at or blanked out
    """
    user = UserFactory.create(name="Madonna", scim_external_id="kc-1")
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    kc_user = UserRepresentation(id="kc-1", firstName="Madonna", lastName=None)
    client = _mock_client(mocker, [[kc_user]])
    client.retrieve.return_value = UserRepresentation(
        id="kc-1",
        firstName="Madonna",
        lastName=None,
        attributes={"fullName": ["Madonna"]},
    )
    remediate_keycloak_user_names.bootstrap_client.return_value = client

    COMMAND.handle(apply=True, limit=None, report_path=None)

    client.save.assert_called_once_with(
        "users/kc-1", {"attributes": {"fullName": ["Madonna"]}}
    )


@pytest.mark.django_db
def test_patch_preserves_other_keycloak_attributes(mocker):
    """Patching fullName must not clobber other custom attributes already on
    the Keycloak record - the admin API PUT replaces the whole attributes
    map, so existing entries have to be merged in, not overwritten
    """
    user = UserFactory.create(name="Joe Smith", scim_external_id="kc-1")
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    kc_user = UserRepresentation(
        id="kc-1",
        firstName="",
        lastName="",
        attributes={"someOtherAttr": ["keep-me"]},
    )
    client = _mock_client(mocker, [[kc_user]])
    client.retrieve.return_value = UserRepresentation(id="kc-1")
    remediate_keycloak_user_names.bootstrap_client.return_value = client

    COMMAND.handle(apply=True, limit=None, report_path=None)

    client.save.assert_called_once_with(
        "users/kc-1",
        {
            "first_name": "Joe",
            "last_name": "Smith",
            "attributes": {"someOtherAttr": ["keep-me"], "fullName": ["Joe Smith"]},
        },
    )


@pytest.mark.django_db
def test_unpatchable_user_has_no_name_data(mocker, tmp_path):
    """A user with no name data anywhere in mitxonline is reported separately,
    never patched even with --apply
    """
    user = UserFactory.create(name="", scim_external_id="kc-1")
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    kc_user = UserRepresentation(id="kc-1", firstName="", lastName="")
    client = _mock_client(mocker, [[kc_user]])
    remediate_keycloak_user_names.bootstrap_client.return_value = client

    report = _run(tmp_path, apply=True, limit=None)

    client.save.assert_not_called()
    assert [row["user_id"] for row in report["unpatchable"]] == [user.id]


@pytest.mark.django_db
def test_limit_caps_writes_in_apply_mode(mocker):
    """--limit caps how many get patched; the rest fall back to would-patch"""
    users = []
    kc_users = []
    for i in range(3):
        user = UserFactory.create(name="Joe Smith", scim_external_id=f"kc-{i}")
        user.legal_address.first_name = "Joe"
        user.legal_address.last_name = "Smith"
        user.legal_address.save()
        users.append(user)
        kc_users.append(UserRepresentation(id=f"kc-{i}", firstName="", lastName=""))

    client = _mock_client(mocker, [kc_users])
    client.retrieve.return_value = UserRepresentation(
        id="kc-0", firstName="Joe", lastName="Smith"
    )
    remediate_keycloak_user_names.bootstrap_client.return_value = client

    COMMAND.handle(apply=True, limit=1, report_path=None)

    assert client.save.call_count == 1


@pytest.mark.django_db
def test_unmatched_keycloak_user_is_ignored(mocker):
    """A Keycloak user with no corresponding mitxonline scim_external_id is
    skipped entirely - not counted in any bucket
    """
    kc_user = UserRepresentation(id="kc-orphan", firstName="", lastName="")
    client = _mock_client(mocker, [[kc_user]])
    remediate_keycloak_user_names.bootstrap_client.return_value = client

    COMMAND.handle(apply=False, limit=None, report_path=None)

    client.save.assert_not_called()


@pytest.mark.django_db
def test_paginates_across_multiple_pages(mocker):
    """The command keeps paging until it gets an empty page back"""
    user = UserFactory.create(name="Joe Smith", scim_external_id="kc-page2")
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    page1 = [
        UserRepresentation(id=f"kc-filler-{i}", firstName="x", lastName="y")
        for i in range(remediate_keycloak_user_names.PAGE_SIZE)
    ]
    page2 = [UserRepresentation(id="kc-page2", firstName="", lastName="")]
    client = _mock_client(mocker, [page1, page2])
    remediate_keycloak_user_names.bootstrap_client.return_value = client

    COMMAND.handle(apply=False, limit=None, report_path=None)

    assert client.list.call_count == 3  # page1, page2, empty terminator
