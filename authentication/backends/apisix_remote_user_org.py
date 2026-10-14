"""
The APISIX Remote User Backend, with organization support.

This should go in the ol-django app. It's here to make it easier to write.
"""

import logging

from django.core.cache import caches
from mitol.apigateway.api import decode_x_header
from mitol.apigateway.backends import ApisixRemoteUserBackend
from mitol.common.utils.datetime import now_in_utc

from b2b.api import reconcile_user_orgs

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

        cache_key = f"user-last-login-time-{user.global_id}"

        if not request.session.get("login_time", False):
            login_time = now_in_utc().isoformat()
            request.session["login_time"] = login_time
            caches["redis"].set(cache_key, login_time)

        apisix_header = decode_x_header(request)

        org_uuids = []

        if apisix_header and "organization" in apisix_header:
            org_uuids = [
                apisix_header["organization"][org]["id"]
                for org in apisix_header["organization"]
            ]

        # Task should check to see if it needs to run or not
        reconcile_user_orgs(user, org_uuids, request=request)

        return user
