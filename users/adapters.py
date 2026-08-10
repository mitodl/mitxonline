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
        ("name", "givenName", None): "legal_address__first_name",
        ("givenName", None, None): "legal_address__first_name",
        ("name", "familyName", None): "legal_address__last_name",
        ("familyName", None, None): "legal_address__last_name",
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

    def _resolve_name(self) -> tuple[str, str]:
        """
        Resolve (given_name, family_name) for the SCIM ``name`` attribute.

        Keycloak has no combined "full name" field - it only stores split
        firstName/lastName, fed by SCIM's name.givenName/name.familyName. So
        whatever single name string we have has to be split into two pieces
        before it's sent; there's no way to hand Keycloak one string and have
        it split for us. Tiers, in order of confidence:

        1. legal_address.first_name/last_name, if both are set - real
           structured data.
        2. self.obj.name, split heuristically (last whitespace-separated
           token = family name, remainder = given name) - no naive split is
           correct for every name (breaks on single-name accounts,
           multi-word surnames, non-Western conventions), but it's the best
           data available for users who only came through the edX migration
           and never had a legal_address name recorded.
        3. Neither available - both empty strings.

        This is deliberately never persisted back onto legal_address, which
        is used for SDN compliance screening - writing a heuristic guess into
        a field that compliance screening may rely on for an accurate legal
        name would be a real risk, not just a data-quality nitpick.
        """
        if self.legal_address.first_name and self.legal_address.last_name:
            return self.legal_address.first_name, self.legal_address.last_name

        given_and_family_name_parts = 2
        full_name = (self.obj.name or "").strip()
        if full_name:
            parts = full_name.rsplit(None, 1)
            if len(parts) == given_and_family_name_parts:
                return parts[0], parts[1]
            return parts[0], ""

        return "", ""

    def to_dict(self):
        """
        Return a ``dict`` conforming to the SCIM User Schema,
        ready for conversion to a JSON object.
        """
        given_name, family_name = self._resolve_name()
        return {
            "id": self.id,
            "externalId": self.obj.scim_external_id,
            "schemas": [SchemaURI.USER],
            "userName": self.obj.username,
            "name": {
                "givenName": given_name,
                "familyName": family_name,
            },
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

        # Inbound name.givenName/familyName always writes to legal_address
        # directly - this is real data from an external SCIM client, never
        # a derived guess (see _resolve_name's tier 2, which is outbound-only).
        # An absent key, an explicit JSON null, or a blank/whitespace-only
        # string are all treated as "no value provided" and leave the
        # existing value alone - legal_address feeds SDN compliance
        # screening, so a client silently sending an empty name should not
        # be able to blank out a previously-valid one.
        name = d.get("name") or {}
        given_name = (name.get("givenName") or "").strip()
        if given_name:
            self.legal_address.first_name = given_name
        family_name = (name.get("familyName") or "").strip()
        if family_name:
            self.legal_address.last_name = family_name

    def _save_related(self):
        self.user_profile.user = self.obj
        self.user_profile.save()

        self.legal_address.user = self.obj
        self.legal_address.save()

        self.openedx_user.user = self.obj
        self.openedx_user.save()
