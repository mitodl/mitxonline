from typing import TYPE_CHECKING

from mitol.scim.adapters import UserAdapter
from mitol.scim.constants import SchemaURI

from openedx.models import OpenEdxUser
from users.models import LegalAddress, UserProfile

if TYPE_CHECKING:
    from users.models import User


class LearnUserAdapter(UserAdapter):
    """
    Custom adapter to extend django_scim library.  This is required in order
    to extend the profiles.models.Profile model to work with the
    django_scim library.
    """

    ATTR_MAP = {
        ("active", None, None): "is_active",
        ("userName", None, None): "username",
        ("fullName", None, None): "name",
    }

    obj: "User"

    user_profile: UserProfile
    legal_address: LegalAddress
    openedx_user: OpenEdxUser

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

    def to_dict(self):
        """
        Return a ``dict`` conforming to the SCIM User Schema,
        ready for conversion to a JSON object.
        """
        return {
            "id": self.id,
            "externalId": self.obj.scim_external_id,
            "schemas": [SchemaURI.USER],
            "userName": self.obj.username,
            "displayName": self.display_name,
            "emails": self.emails,
            "active": self.obj.is_active,
            "groups": [],
            "meta": self.meta,
        }

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
        self.parse_emails(d.get("emails"))

        self.obj.is_active = d.get("active", True)
        self.obj.username = d.get("userName")
        self.obj.scim_username = d.get("userName")
        self.obj.scim_external_id = d.get("externalId")
        self.obj.global_id = self.obj.scim_external_id or ""
        self.obj.name = d.get("fullName", self.obj.name)

    def _save_related(self):
        self.user_profile.user = self.obj
        self.user_profile.save()

        self.legal_address.user = self.obj
        self.legal_address.save()

        self.openedx_user.user = self.obj
        self.openedx_user.save()
