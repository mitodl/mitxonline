import logging
from typing import TYPE_CHECKING

from mitol.scim.adapters import UserAdapter

from b2b.api import reconcile_user_orgs
from b2b.models import OrganizationPage
from openedx.models import OpenEdxUser
from users.models import LegalAddress, UserProfile

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from users.models import User


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
    groups: list[dict] = []

    def __init__(self, obj, request=None):
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
        super().from_dict(d)

        self.obj.name = d.get("fullName", self.obj.name)  # name's default is ""

        first_name = d.get("name", {}).get("given_name", "")
        if first_name:
            self.legal_address.first_name = first_name

        last_name = d.get("name", {}).get("last_name", "")
        if last_name:
            self.legal_address.last_name = last_name

        groups = d.get("groups", None)
        if groups:
            self.groups = groups

    def _save_related(self):
        self.user_profile.user = self.obj
        self.user_profile.save()

        self.legal_address.user = self.obj
        self.legal_address.save()

        self.openedx_user.user = self.obj
        self.openedx_user.save()

        if self.groups:
            log.info("saving groups for %s: %s", self.obj, self.groups)
            group_keys = [
                group["display"]
                for group in self.groups
                if group["type"] == "organization"
            ]
            log.info("keys to update: %s", group_keys)
            group_sso_ids = (
                OrganizationPage.objects.filter(org_key__in=group_keys)
                .all()
                .values_list("sso_organization_id", flat=True)
            )
            created, removed = reconcile_user_orgs(self.obj, group_sso_ids)
            log.info("%s groups created %s groups removed", created, removed)
