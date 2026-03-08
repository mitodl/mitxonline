"""Project conftest"""

import uuid

import pytest
from faker import Faker
from faker.providers import BaseProvider
from hubspot.crm.objects import SimplePublicObject
from opaque_keys.edx.keys import CourseKey

from fixtures.b2b import *  # noqa: F403
from fixtures.common import *  # noqa: F403
from hubspot_sync.conftest import FAKE_HUBSPOT_ID
from main import features


@pytest.fixture(autouse=True)
def default_settings(monkeypatch, settings):
    """Set default settings for all tests"""
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "main.settings")

    settings.FEATURES[features.IGNORE_EDX_FAILURES] = False
    settings.FEATURES[features.SYNC_ON_DASHBOARD_LOAD] = False


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
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY = "Test Security Key"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY = "Test Access Key"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def mock_hubspot_api(mocker):
    """Mock the Hubspot CRM API"""
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
    faker = Faker()
    faker.add_provider(CourseKeyProvider)

    return faker


class CourseKeyProvider(BaseProvider):
    """Generates fake course keys (readable ID/courseware ID)."""

    def coursekey(self, *, keytype: str | None = "course") -> str:
        """
        Generate and return a fake course key, ensuring that it is "valid".

        Program keys aren't technically valid because programs don't exist in the
        edX opaque key system, but it'll at least be in the proper format.

        Args:
            keytype (str): what kind of key to generate (course or program, default course)
        Returns:
            str, the course key
        """

        org_part = self.random_uppercase_letters(length=3)
        course_major = self.random_int(1, 99)
        course_minor = self.hexify("^^^^x", upper=True)
        semester_index = self.random_digit_above_two()
        semester_year = self.random_int(1900, 3000)

        key_object = str(
            CourseKey(
                {
                    "org": f"Py{org_part}",
                    "course": f"{course_major}.{course_minor}",
                    "run": f"{semester_index}T{semester_year}",
                }
            )
        )

        if keytype == "program":
            key_object = key_object.replace("course-v1", "program-v1")

        return key_object
