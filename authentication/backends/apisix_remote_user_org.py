"""
The APISIX Remote User Backend, with organization support.

This should go in the ol-django app. It's here to make it easier to write.
"""

import logging

from mitol.apigateway.api import decode_x_header
from mitol.apigateway.backends import ApisixRemoteUserBackend

from b2b.tasks import queue_reconcile_user_orgs

log = logging.getLogger(__name__)


class ApisixRemoteUserOrgBackend(ApisixRemoteUserBackend):
    """
    Updates the APISIX remote user backend to work with organizations.

    We should get the organizations that the user belongs to in the APISIX
    payload, so we should reconcile them (occasionally, maybe) when the user gets
    here. SCIM should also take care of this but we won't necessarily have that
    for local deployments.
    """

    def configure_user(self, request, user, *args, created=True):
        """Configure the user, then reconcile the orgs."""

        user = super().configure_user(request, user, *args, created=created)

        apisix_header = decode_x_header(request)

        org_uuids = []

        if apisix_header and "organization" in apisix_header:
            org_uuids = [
                apisix_header["organization"][org]["id"]
                for org in apisix_header["organization"]
            ]

        if sorted(org_uuids) != sorted(user.b2b_organization_sso_ids):
            # Only bother with this if we need to (and pass it off to Celery if we do)
            queue_reconcile_user_orgs.delay(user.id, org_uuids)

        return user
