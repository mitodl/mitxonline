"""Tests for compliance admin views"""

import pytest
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.urls import reverse

from compliance.factories import ExportComplianceLogFactory
from compliance.models import ExportComplianceDecision

pytestmark = [pytest.mark.django_db]


def _action_url(log_entry):
    """Build the django-object-actions change-page action URL for a log"""
    return reverse(
        "admin:compliance_exportcompliancelog_actions",
        args=(log_entry.pk, "mark_manually_approved"),
    )


def test_mark_manually_approved_action(client, admin_user):
    """The action should set decision/approved_by/approved_on for the log"""
    client.force_login(admin_user)
    log_entry = ExportComplianceLogFactory.create(
        decision=ExportComplianceDecision.DECLINED
    )

    response = client.get(_action_url(log_entry), follow=True)

    assert response.status_code == 200
    log_entry.refresh_from_db()
    assert log_entry.decision == ExportComplianceDecision.MANUALLY_APPROVED
    assert log_entry.approved_by == admin_user
    assert log_entry.approved_on is not None


def test_mark_manually_approved_action_reports_validation_errors(
    client, admin_user, mocker
):
    """A ValidationError from full_clean should be reported and the record left untouched"""
    client.force_login(admin_user)
    log_entry = ExportComplianceLogFactory.create(
        decision=ExportComplianceDecision.DECLINED
    )
    mocker.patch(
        "compliance.models.ExportComplianceLog.full_clean",
        side_effect=ValidationError("boom"),
    )

    response = client.get(_action_url(log_entry), follow=True)

    assert response.status_code == 200
    messages = [str(message) for message in get_messages(response.wsgi_request)]
    assert any("boom" in message for message in messages)
    log_entry.refresh_from_db()
    assert log_entry.decision == ExportComplianceDecision.DECLINED
    assert log_entry.approved_by is None
    assert log_entry.approved_on is None


def test_mark_manually_approved_action_not_on_changelist(client, admin_user):
    """The action should not be selectable from the changelist bulk actions dropdown"""
    client.force_login(admin_user)
    ExportComplianceLogFactory.create(decision=ExportComplianceDecision.DECLINED)

    response = client.get(reverse("admin:compliance_exportcompliancelog_changelist"))

    assert response.status_code == 200
    # No changelist actions are registered at all, so Django omits the bulk
    # actions dropdown entirely - the strongest possible signal that
    # mark_manually_approved isn't reachable from this page.
    assert response.context["action_form"] is None
    assert b"mark_manually_approved" not in response.content
