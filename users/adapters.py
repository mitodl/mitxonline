from mitol.scim.adapters import UserAdapter

from users.models import UserProfile


class LearnUserAdapter(UserAdapter):
    """
    Custom adapter to extend django_scim library.  This is required in order
    to extend the profiles.models.Profile model to work with the
    django_scim library.
    """
    ATTR_MAP = UserAdapter.ATTR_MAP | {
        ("fullName", None, None): "name",
    }

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

        self.obj.name = d.get("fullName", d.get("name", ""))
        self.obj.user_profile = getattr(self.obj, "user_profile", UserProfile())
        self.obj.legal_address = getattr(self.obj, "legal_address", LegalAddress())
        self.obj.legal_address.first_name = d.get("name", {}).get("given_name", "")
        self.obj.legal_address.last_name = d.get("name", {}).get("last_name", "")

    def save_related(self):
        self.obj.user_profile.user = self.obj
        self.obj.user_profile.save()
        self.obj.legal_address.user = self.obj
        self.obj.legal_address.save()
