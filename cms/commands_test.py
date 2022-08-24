"""Tests for CMS management commands"""
from django.core.management import call_command


def test_configure_wagtail(mocker):
    """The 'configure_wagtail' command should call specific API methods to configure Wagtail"""
    patched_ensure_home_page = mocker.patch(
        "cms.management.commands.configure_wagtail.ensure_home_page_and_site"
    )
    patched_ensure_resource_pages = mocker.patch(
        "cms.management.commands.configure_wagtail.ensure_resource_pages"
    )
    patched_ensure_product_index = mocker.patch(
        "cms.management.commands.configure_wagtail.ensure_product_index"
    )
    patched_ensure_program_product_index = mocker.patch(
        "cms.management.commands.configure_wagtail.ensure_program_product_index"
    )
    patched_ensure_signatory_index = mocker.patch(
        "cms.management.commands.configure_wagtail.ensure_signatory_index"
    )
    patched_ensure_certificate_index = mocker.patch(
        "cms.management.commands.configure_wagtail.ensure_certificate_index"
    )
    call_command("configure_wagtail")
    patched_ensure_home_page.assert_called_once()
    patched_ensure_resource_pages.assert_called_once()
    patched_ensure_product_index.assert_called_once()
    patched_ensure_program_product_index.assert_called_once()
    patched_ensure_signatory_index.assert_called_once()
    patched_ensure_certificate_index.assert_called_once()
