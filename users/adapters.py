from functools import partial
from typing import TYPE_CHECKING

from django.db import transaction
from mitol.scim.adapters import UserAdapter
from mitol.scim.constants import SchemaURI

from openedx.models import OpenEdxUser
from users.models import LegalAddress, UserProfile

if TYPE_CHECKING:
    from users.models import User

#: Attributes whose change queues update_edx_user_profile.
EDX_PROFILE_SYNC_ATTRS = frozenset({"fullName", "name", "displayName"})

#: Separate from the profile attrs because update_edx_user_email re-runs the
#: Open edX OAuth handshake rather than PATCHing - edX treats email as read-only.
EDX_EMAIL_SYNC_ATTRS = frozenset({"emails"})

#: Allow-list on purpose: a SCIM client may send attributes we do not model, and
#: nothing outside this set may queue Open edX work.
EDX_SYNC_ATTRS = EDX_PROFILE_SYNC_ATTRS | EDX_EMAIL_SYNC_ATTRS

#: Deliberately not synced. id/schemas/groups/externalId are protocol
#: scaffolding; meta changes on every save. userName and active are real data,
#: but edX lists both in AccountUserSerializer.read_only_fields and 400s the
#: whole PATCH on a read-only key, which would take the name sync with it - and
#: it exposes no reactivate endpoint, so active could only ever sync one-way.
#: test_edx_sync_attrs_cover_to_dict asserts this plus EDX_SYNC_ATTRS covers
#: to_dict(), so a new attribute fails the suite instead of being dropped.
EDX_UNSYNCED_ATTRS = frozenset(
    {"id", "schemas", "groups", "externalId", "meta", "userName", "active"}
)


class LearnUserAdapter(UserAdapter):
    """
    Custom adapter to extend django_scim library.  This is required in order
    to extend the profiles.models.Profile model to work with the
    django_scim library.
    """

    # name.givenName/familyName are deliberately absent here. django_scim's
    # handle_replace() resolves a PATCH path through this map with a plain
    # setattr(self.obj, ATTR_MAP[path], value) - it never walks a "__"
    # double-underscore path into a related object, so a mapping to
    # "legal_address__first_name" would silently set a bogus flat attribute
    # of that literal name on the user instead of touching
    # legal_address.first_name, and never raise. from_dict() (used for a
    # full create/replace) already handles name.givenName/familyName
    # correctly by writing to self.legal_address directly - a PATCH-by-path
    # replace of just the name is not supported and correctly falls through
    # to handle_replace's NotImplementedError instead.
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

        # __init__ runs before from_dict()/handle_replace() mutate the object and
        # the view calls save() on this same instance, so this is a valid
        # pre-change baseline. Creates have nothing to diff and no edX account yet.
        self._edx_sync_is_new = self.is_new_user
        self._edx_sync_snapshot_before = (
            None if self.is_new_user else self._edx_sync_snapshot()
        )
        self._edx_profile_sync_queued = False

    def _edx_sync_snapshot(self) -> dict:
        """
        Snapshot the Open edX-relevant SCIM attributes, for diffing across a save.

        Reading through _scim_attrs() means the diff follows the adapter's schema,
        so LegalAddress-backed name.givenName is covered like any other attribute.
        """
        snapshot = self._scim_attrs()
        return {key: snapshot.get(key) for key in EDX_SYNC_ATTRS}

    @property
    def display_name(self):
        """
        Return the displayName of the user per the SCIM spec.
        """
        return self.obj.name

    def _resolve_name(self) -> tuple[str, str]:
        """
        Resolve (given_name, family_name) for the SCIM ``name`` attribute.

        Only returns legal_address.first_name/last_name, and only when both
        are set - real structured data, never a guess. A single full-name
        string can't be reliably split into given/family (breaks on
        single-name accounts, multi-word surnames, non-Western conventions),
        so when legal_address doesn't have both parts this returns
        ("", "") rather than guessing. The full name itself is still sent
        outbound on its own via the "fullName" attribute (see to_dict), so
        nothing is lost for users - most commonly those who only came
        through the edX migration - who have a full name but no
        legal_address split on file.
        """
        if self.legal_address.first_name and self.legal_address.last_name:
            return self.legal_address.first_name, self.legal_address.last_name
        return "", ""

    def _scim_attrs(self) -> dict:
        """
        Return the user-data portion of the SCIM representation.

        Split out of to_dict() so change detection can diff it without touching
        ``meta``, whose lastModified changes on every save and whose location
        needs a request the management commands building this adapter lack.
        """
        given_name, family_name = self._resolve_name()
        return {
            "id": self.id,
            "externalId": self.obj.scim_external_id,
            "schemas": [SchemaURI.USER],
            "userName": self.obj.username,
            "fullName": self.obj.name,
            "name": {
                "givenName": given_name,
                "familyName": family_name,
            },
            "displayName": self.display_name,
            "emails": self.emails,
            "active": self.obj.is_active,
            "groups": [],
        }

    def to_dict(self):
        """
        Return a ``dict`` conforming to the SCIM User Schema,
        ready for conversion to a JSON object.
        """
        return {**self._scim_attrs(), "meta": self.meta}

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

    def save(self):
        """
        Persist the user, then mirror any changed fields into Open edX.

        The single choke point for every inbound SCIM write: PUT/POST reach it via
        from_dict(), PATCH via handle_replace(), and /Bulk by re-dispatching
        through those views. Queueing never raises - a SCIM client must not see a
        500 because the broker or edX is down.
        """
        from openedx.task_helpers import (  # noqa: PLC0415
            queue_edx_user_email_change,
            queue_edx_user_profile_update,
        )

        before = self._edx_sync_snapshot_before
        super().save()

        if self._edx_sync_is_new:
            return

        after = self._edx_sync_snapshot()
        # handle_operations() calls save() once per PATCH operation, so re-baseline
        # or every later save re-diffs against the values the request started with.
        self._edx_sync_snapshot_before = after

        changed = {key for key in EDX_SYNC_ATTRS if before.get(key) != after.get(key)}
        if not changed:
            return

        # on_commit, not inline: PatchView.patch and super().save() both open atomic
        # blocks, so a worker could otherwise read the row before it is committed.
        if changed & EDX_PROFILE_SYNC_ATTRS and not self._edx_profile_sync_queued:
            self._edx_profile_sync_queued = True
            transaction.on_commit(partial(queue_edx_user_profile_update, self.obj))

        if changed & EDX_EMAIL_SYNC_ATTRS:
            transaction.on_commit(partial(queue_edx_user_email_change, self.obj))
