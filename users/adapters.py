from typing import TYPE_CHECKING

from b2b.models import ContractPage
from mitol.scim.adapters import UserAdapter

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

    ATTR_MAP = UserAdapter.ATTR_MAP | {
        ("fullName", None, None): "name",
    }

    obj: "User"

    user_profile: UserProfile
    legal_address: LegalAddress
    openedx_user: OpenEdxUser
    b2b_contracts: ContractPage

    def __init__(self, obj, request=None):
        super().__init__(obj, request=request)

        self.user_profile = self.obj.user_profile = getattr(
            self.obj, "user_profile", UserProfile()
        )

        try:
            self.legal_address = self.obj.legal_address  # triggers DB fetch if needed
        except LegalAddress.DoesNotExist:
            self.legal_address = LegalAddress()

        self.b2b_contracts = self.obj.b2b_contracts

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

        Note: This method does NOT save the user object. To persist changes,
        call ``.save()`` on the adapter.
        """
        super().from_dict(d)

        self.obj.name = d.get("fullName", "")

        name_data = d.get("name", {})

        self.legal_address.first_name = name_data.get("given_name") or self.legal_address.first_name
        self.legal_address.last_name = name_data.get("last_name") or self.legal_address.last_name


        organization_name = d.get("organization")
        if organization_name:
            contract_pages = ContractPage.objects.filter(organization__name=organization_name)
            self.obj.b2b_contracts.add(*contract_pages)

    def _save_related(self):
        self.user_profile.user = self.obj
        self.user_profile.save()

        self.legal_address.user = self.obj
        self.legal_address.save()

        self.openedx_user.user = self.obj
        self.openedx_user.save()
