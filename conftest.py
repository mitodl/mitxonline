"""Project conftest"""

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from faker import Faker
from hubspot.crm.objects import SimplePublicObject
from nacl.encoding import Base64Encoder
from nacl.public import PrivateKey

# auto load in fixtures
pytest_plugins = [
    str(fixture).replace("/", ".").replace(".py", "")
    for fixture in Path().glob("fixtures/*.py")
    if fixture.name != "__init__.py"
]


@pytest.fixture(autouse=True)
def default_settings(monkeypatch, settings):
    """Set default settings for all tests"""
    from main import features  # noqa: PLC0415

    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "main.settings")

    settings.FEATURES[features.IGNORE_EDX_FAILURES] = False
    settings.FEATURES[features.SYNC_ON_DASHBOARD_LOAD] = False
    settings.FEATURES[features.ENABLE_PROGRAM_SPECIFIC_PATHWAY_SCHOOLS] = False
    settings.FEATURES[features.STRIPE_ENABLE_FEATURE_FLAG] = False
    settings.FEATURES[features.EXPORT_COMPLIANCE_CHECK_ENABLED] = True


@pytest.fixture(autouse=True)
def mocked_product_signal(mocker):
    """Mock hubspot_sync signals"""
    mocker.patch("ecommerce.signals.sync_hubspot_product")


@pytest.fixture(autouse=True)
def mocked_flexibleprice_signal(mocker):
    """Mock FlexiblePrice signals"""
    mocker.patch("flexiblepricing.tasks.get_ecommerce_products_by_courseware_name")


@pytest.fixture(autouse=True)
def payment_gateway_settings(settings):
    """Set default CyberSource settings for tests."""
    settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY = "CyberSource"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY = "Test Security Key"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY = "Test Access Key"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID = uuid.uuid4()
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID = "merchant-id"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID = uuid.uuid4().hex
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET = uuid.uuid4().hex
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT = (
        "apitest.cybersource.com"
    )


@pytest.fixture
def export_compliance_keypair(settings):
    """Provide an ephemeral NaCl keypair for encrypting/decrypting cached export compliance data in tests."""
    private_key = PrivateKey.generate()
    settings.CYBERSOURCE_INQUIRY_LOG_NACL_ENCRYPTION_KEY = Base64Encoder.encode(
        bytes(private_key.public_key)
    ).decode("ascii")
    return private_key


@pytest.fixture(autouse=True)
def mocked_export_compliance(mocker):
    """Mock export compliance checks in shared enrollment helpers by default."""
    return mocker.patch(
        "courses.api.verify_user_with_exports",
        return_value=SimpleNamespace(
            accepted=True,
            decision="ACCEPT",
            reason_code=100,
            request_id="test-request-id",
        ),
    )


@pytest.fixture(autouse=True)
def mock_hubspot_api(mocker):
    """Mock the Hubspot CRM API"""
    from hubspot_sync.conftest import FAKE_HUBSPOT_ID  # noqa: PLC0415

    mock_api = mocker.patch("mitol.hubspot_api.api.HubspotApi")
    mock_api.return_value.crm.objects.basic_api.create.return_value = (
        SimplePublicObject(id=FAKE_HUBSPOT_ID)
    )
    return mock_api


def pytest_addoption(parser):
    """Pytest hook that adds command line parameters"""
    parser.addoption(
        "--simple",
        action="store_true",
        help="Run tests only (no cov, warning output silenced)",
    )


def pytest_cmdline_main(config):
    """Pytest hook that runs after command line options are parsed"""
    if config.option.simple is True:
        config.option.pylint = False
        config.option.no_pylint = True


def pytest_configure(config):
    """Pytest hook to perform some initial configuration"""
    if config.option.simple is True:
        # NOTE: These plugins are already configured by the time the pytest_cmdline_main hook is run, so we can't
        #       simply add/alter the command line options in that hook. This hook is being used to
        #       reconfigure/unregister plugins that we can't change via the pytest_cmdline_main hook.
        # Switch off coverage plugin
        cov = config.pluginmanager.get_plugin("_cov")
        cov.options.no_cov = True
        # Remove warnings plugin to suppress warnings
        if config.pluginmanager.has_plugin("warnings"):
            warnings_plugin = config.pluginmanager.get_plugin("warnings")
            config.pluginmanager.unregister(warnings_plugin)


@pytest.fixture(autouse=True, scope="module")
def fake() -> Faker:
    """Fixture to provide a Faker instance"""

    return Faker()


# Tests marked django_db(transaction=True) get TransactionTestCase semantics:
# teardown flushes (TRUNCATEs) every table, wiping rows created by data
# migrations (Wagtail's default Locale, the root Pages). Nothing recreates
# those rows on a reused test database, so a run containing any transactional
# test leaves the DB unusable for the next `--reuse-db` run (mass
# Locale.DoesNotExist). Django accepted this as a bug but never landed a fix
# (https://code.djangoproject.com/ticket/25251), and pytest-django's
# serialized_rollback only restores *before* a test that declares it, never
# after the session's last flush. So: snapshot the freshly migrated DB once
# per session and restore it after every transactional test's flush.
_migration_data = SimpleNamespace(snapshot=None, blocker=None)

# Sentinel for detecting a DB that lost its data-migration rows. Any row that
# exists only because a data migration created it works here; the repair
# machinery itself is agnostic about which rows the migrations create. This
# one is Wagtail's default Locale, whose absence is also the first loud
# symptom of the broken state (Locale.DoesNotExist).
_DATA_MIGRATION_ROW_SENTINEL = '"model": "wagtailcore.locale"'


def _is_transactional_db_test(item) -> bool:
    """Mirror the detection in pytest_django.plugin.pytest_collection_modifyitems."""
    import django.test  # noqa: PLC0415

    cls = getattr(item, "cls", None)
    if cls is not None and issubclass(cls, django.test.TransactionTestCase):
        return not issubclass(cls, django.test.TestCase)
    marker = item.get_closest_marker("django_db")
    if marker and (
        marker.kwargs.get("transaction") or marker.kwargs.get("reset_sequences")
    ):
        return True
    fixturenames = getattr(item, "fixturenames", ())
    return bool(
        {"transactional_db", "live_server", "django_db_reset_sequences"}.intersection(
            fixturenames
        )
    )


@pytest.fixture(autouse=True, scope="session")
def _snapshot_migration_data(request, django_db_blocker):
    """Serialize the post-migration DB state for the pytest_runtest_teardown wrapper."""
    if not any(_is_transactional_db_test(item) for item in request.session.items):
        return
    from django.db import connection  # noqa: PLC0415

    request.getfixturevalue("django_db_setup")
    with django_db_blocker.unblock():
        snapshot = connection.creation.serialize_db_to_string()
    # A missing sentinel row means a previous run died mid-repair and left the
    # DB truncated; snapshot nothing rather than cement the broken state.
    if _DATA_MIGRATION_ROW_SENTINEL not in snapshot:
        pytest.exit(
            "Test database is missing data-migration rows (a previous run was "
            "killed mid-repair). Re-run with --create-db.",
            returncode=3,
        )
    _migration_data.snapshot = snapshot
    _migration_data.blocker = django_db_blocker


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item):
    """Restore data-migration rows after a transactional test's flush.

    This must be a hook wrapper, not a fixture: the flush runs in
    pytest-django's fixture finalizer, and fixture teardown ordering (LIFO)
    cannot guarantee running after it.
    """
    result = yield
    if _migration_data.snapshot is not None and _is_transactional_db_test(item):
        from django.core.management import call_command  # noqa: PLC0415
        from django.db import connection  # noqa: PLC0415

        with _migration_data.blocker.unblock():
            # TransactionTestCase's own flush re-fires post_migrate, which
            # recreates content types and permissions under new pks; those
            # rows collide with the snapshot's on their natural unique keys.
            # Flush again without post_migrate so deserialize starts empty,
            # the same pairing TransactionTestCase uses for
            # serialized_rollback (django/test/testcases.py `_fixture_teardown`).
            call_command(
                "flush",
                verbosity=0,
                interactive=False,
                database=connection.alias,
                reset_sequences=False,
                inhibit_post_migrate=True,
            )
            connection.creation.deserialize_db_from_string(_migration_data.snapshot)
    return result
