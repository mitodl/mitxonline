import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django_scim.adapters import SCIMGroup
from mitol.scim.adapters import UserAdapter

from openedx.models import OpenEdxUser
from users.models import LegalAddress, UserProfile

if TYPE_CHECKING:
    from users.models import User

log = logging.getLogger(__name__)


class LearnGroupAdapter(SCIMGroup):
    """
    Custom adapter for SCIMGroups that just fixes the endpoint URL.
    """

    @classmethod
    def resource_type_dict(cls, request=None):
        """Return the resource type info, but fix the endpoint."""

        resource_type = super().resource_type_dict(request)

        return {
            **resource_type,
            "endpoint": resource_type["endpoint"].replace(
                settings.MITXONLINE_SCIM_RESOURCE_PREFIX, ""
            ),
        }


class LearnUserAdapter(UserAdapter):
    """
    Custom adapter to extend django_scim library.  This is required in order
    to extend the profiles.models.Profile model to work with the
    django_scim library.
    """

    ATTR_MAP = UserAdapter.ATTR_MAP | {
        ("fullName", None, None): "name",
    }

    obj: "User"

    user_profile: UserProfile
    legal_address: LegalAddress
    openedx_user: OpenEdxUser

    def __init__(self, obj, request=None):
        log.warning("adapter obj: %s", obj)
        if request:
            log.warning("adapter request post: %s", request.POST)
            log.warning("adapter request get : %s", request.GET)

        super().__init__(obj, request=request)

        self.user_profile = self.obj.user_profile = getattr(
            self.obj, "user_profile", UserProfile()
        )

        self.legal_address = self.obj.legal_address = getattr(
            self.obj, "legal_address", LegalAddress()
        )

        self.openedx_user = self.obj.openedx_user
        if self.openedx_user is None:
            del self.obj.openedx_user
            self.openedx_user = self.obj.openedx_user = OpenEdxUser()

    @property
    def display_name(self):
        """
        Return the displayName of the user per the SCIM spec.
        """
        return self.obj.name

    def from_dict(self, d):
        """
        Consume a ``dict`` conforming to the SCIM User Schema, updating the
        internal user object with data from the ``dict``.

        Please note, the user object is not saved within this method. To
        persist the changes made by this method, please call ``.save()`` on the
        adapter. Eg::

            scim_user.from_dict(d)
            scim_user.save()
        """
        log.warning("from_dict: dict: %s", d)

        super().from_dict(d)

        self.obj.name = d.get("fullName", self.obj.name)  # name's default is ""

        first_name = d.get("name", {}).get("given_name", "")
        if first_name:
            self.legal_address.first_name = first_name

        last_name = d.get("name", {}).get("last_name", "")
        if last_name:
            self.legal_address.last_name = last_name

    def _save_related(self):
        self.user_profile.user = self.obj
        self.user_profile.save()

        self.legal_address.user = self.obj
        self.legal_address.save()

        self.openedx_user.user = self.obj
        self.openedx_user.save()

    @classmethod
    def resource_type_dict(cls, request=None):
        """
        Return the resource type info, but fix the endpoint.

        SCIM for Keycloak appends the "endpoint" in the resource type dict to
        the end of the base URL. For whatever reason, it does this correctly for
        other things, but it doesn't for Resources. Also, you can't specify a
        full URL. It's relative or nothing.

        So, set MITXONLINE_SCIM_RESOURCE_PREFIX to whatever the base path for the
        SCIM v2 API is so we can remove it and SCIM for Keycloak can maybe be
        happy.
        """

        resource_type = super().resource_type_dict(request)

        return {
            **resource_type,
            "endpoint": resource_type["endpoint"].replace(
                settings.MITXONLINE_SCIM_RESOURCE_PREFIX, ""
            ),
        }

    def parse_scim_for_keycloak_payload(self, payload: str) -> dict:
        """Wrap this in some logging"""

        log.warning("parse_scim_for_keycloak_payload: payload: %s", payload)

        result = super().parse_scim_for_keycloak_payload(payload)

        log.warning("parse_scim_for_keycloak_payload: result: %s", result)
        return result

    def parse_path_and_values(self, path, value):
        """Wrap this in logging too"""

        log.warning("parse_path_and_values: path: %s", path)
        log.warning("parse_path_and_values: value: %s", value)

        results = super().parse_path_and_values(path, value)

        log.warning("parse_path_and_values: results: %s", results)
        return results
