# ruff: noqa: PLC0415
"""Tasks for the B2B app."""

from main.celery import app


@app.task()
def queue_enrollment_code_check(contract_id: int):
    """Queue the ensure_enrollment_codes_exist call."""
    from b2b.api import ensure_enrollment_codes_exist
    from b2b.models import ContractPage

    contract = ContractPage.objects.get(id=contract_id)
    ensure_enrollment_codes_exist(contract)


@app.task()
def queue_reconcile_user_orgs(user_id, orgs):
    """Queue the reconcile_user_orgs call (which is potentially expensive.)"""

    from django.contrib.auth import get_user_model

    from b2b.api import reconcile_user_orgs

    reconcile_user = get_user_model().objects.get(pk=user_id)
    reconcile_user_orgs(reconcile_user, orgs)
