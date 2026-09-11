# B2B Provisioning API (C1) — implementation spec

Status: implemented, in review. Design RFC:
<https://github.com/mitodl/hq/discussions/12784>

This is the phase-1 implementation spec for the runtime provisioning API that
takes ownership of per-customer Keycloak resources from Pulumi. It is a
staff-only API surface; the partner-facing self-service wizard (C2) is a later
UI built on top of it and is out of scope here.

Built as a five-PR stack (mitodl/mitxonline stack #3933), bottom to top:
mitodl/mitxonline#3928 (Keycloak client), #3929 (data model), #3930 (the
provisioning module), #3931 (the HTTP surface), #3932 (retiring the manual
paths). This document has been revised against what was actually built; where
implementation found the original spec wrong, it says so rather than quietly
reading as though it had been right all along.

## Why this exists

Onboarding a B2B customer today is nine manual steps across four repositories,
with no system of record for how far along any given customer is. Two of those
steps are the ones this API replaces:

- Creating the Keycloak organization, its verified domains, its identity
  provider, and the IdP's attribute mappers. Today this is either console work
  or a Pulumi PR per customer against
  `ol-infrastructure/src/ol_infrastructure/substructure/keycloak/olapps.py`.
- Getting that organization into MITx Online, which happens only when
  `reconcile_keycloak_orgs()` next runs — a Celery beat job on a
  `KEYCLOAK_ORG_SYNC_FREQUENCY` of 86400 seconds (`main/settings.py:981`,
  schedule entry at `main/settings.py:1052`). A customer created just after a
  sync is invisible to MITx Online for up to 24 hours.

Everything else in the sequence (courseware import, contract creation,
enrollment codes, manager designation) stays as it is for phase 1. See
`common_workflows.md` for the full current sequence.

## Ownership boundary

The core design decision is a substrate/tenant split:

| Owner | Resources |
| --- | --- |
| Pulumi (`ol-infrastructure`) | realm, authentication flows, client scopes, clients, service-account role grants |
| This API (`mitxonline/b2b`) | Keycloak organizations, organization domains, identity providers, IdP attribute mappers, org↔IdP links, organization groups, plus the `OrganizationPage` / `ContractPage` records and the onboarding state |

Two systems can currently write per-customer Keycloak resources. That sounds
like it blocks everything here. It does not, and the reason is worth being
precise about, because the original draft of this spec got it wrong.

**Pulumi only deletes resources that are in its own state.** An organization
created through this API was never in Pulumi state, so Pulumi does not see it,
does not diff it, and will not delete it. Therefore:

- New partners can be onboarded through this API immediately, with no migration
  and no risk to the Pulumi-managed set.
- The migration matters only for the organizations **already** in Pulumi state,
  and only when someone wants to modify one of them outside Pulumi. Left alone
  they keep working indefinitely.

The real cross-system hazard is **alias collision, not deletion**. Keycloak
organization and IdP aliases are realm-wide, so an alias this API creates will
break a later Pulumi declaration of the same name — a failed `pulumi up` rather
than a lost integration, but a production deploy failure all the same. That
guard belongs here, not in the migration: reject an alias already present in the
realm before creating anything.

The handover itself is tracked separately
(`tk-migrate-per-org-keycloak-resources-out-of-pulumi-632a53`). Its scope,
measured against the Production stack on 2026-09-03, is 109 of 353 resources:
24 organizations, 15 SAML IdPs, 10 OIDC IdPs, 59 attribute-importer mappers and
one hardcoded-attribute mapper. Note the design assumed per-organization
**groups** were part of the tenant set; they are not — the realm has exactly one
group (`ol-mit-moira-group`).

The ordering constraint that does hold: **the API must be able to read and
manage the existing resources before Pulumi stops declaring them, and neither
system may delete a live partner integration during the handover.**

## What already exists

More of the foundation is in place than the manual process suggests.

**Admin API client.** `b2b/keycloak_admin_api.py` has a generic client and a
`KeycloakAdminModel` wrapper over it: `list` (`:328`), `get` (`:347`),
`associate` (`:363`) and `disassociate` (`:381`). `associate`/`disassociate`
POST/DELETE against `{endpoint}/{parent_id}/{association_type}/{child_id}`,
which is exactly the shape of the org↔IdP link
(`organizations/{id}/identity-providers`). The client underneath also has
`create` (`:222`, POST returning a parsed representation) and `save` (`:241`,
PUT returning a bare success).

**Typed representations.** `b2b/keycloak_admin_dataclasses.py` is generated
from Keycloak's published OpenAPI spec and already contains
`IdentityProviderRepresentation` (`:414`),
`IdentityProviderMapperRepresentation` (`:388`),
`OrganizationDomainRepresentation` (`:506`) and `OrganizationRepresentation`
(`:1219`). No new hand-written models are needed for the Keycloak side.

**Service account permissions — verified, no longer a prerequisite.**
`mitxonline-b2b-client` held only `view-realm`, `view-users`, `query-users` and
`manage-realm`. `manage-realm` covers Keycloak Organizations but not identity
providers, so every IdP call returned 403 and the client could not even list an
organization's IdPs.
[ol-infrastructure#5730](https://github.com/mitodl/ol-infrastructure/pull/5730)
added `manage-identity-providers` and `view-identity-providers`; it merged and
deployed to CI, QA and Production on 2026-09-03.

Confirmed live against the QA realm the same day, as `mitxonline-b2b-client`:

| Call | Result |
| --- | --- |
| `GET identity-provider/instances` | 200, 4 realm IdPs |
| `GET identity-provider/instances/{alias}` | 200 |
| `GET organizations/{id}/identity-providers` | 200 on every org; the `mit` org returns a real linked IdP |
| `POST identity-provider/import-config` | 200, 16 parsed config keys |

`import-config` was additionally confirmed against an **external** metadata URL
(`https://sso.ol.mit.edu/realms/olapps/protocol/saml/descriptor`), returning a
correctly parsed `idpEntityId`, `singleSignOnServiceUrl` and signing
certificate. That matters separately from authorization: parsing the realm's own
descriptor proves the permission, but only an external fetch proves Keycloak's
outbound egress works, which is what partner onboarding actually depends on.

One limit worth knowing: the service account **cannot introspect its own role
mappings** — `GET clients?clientId=...` returns 403, since it holds `view-realm`
but not `view-clients`. Verify capability by calling endpoints, not by reading a
role list.

**Declarative contract blueprint.** `b2b_contract export` / `import`
(mitodl/mitxonline#3686) is the existing declarative primitive and the natural
foundation for the phase-2 contract saga. Phase 1 does not change it.

## Client gaps to close

This spec originally named three additions to `KeycloakAdminModel`. Building it
found six, and the three extra ones are not conveniences — without them the
saga below cannot be written at all. All belong in `b2b/keycloak_admin_api.py`
alongside the existing methods.

1. **`update(item_id, data)`** — PUT to `{endpoint}/{item_id}`. `save` on the
   client takes a full URL path, so the model-level convenience is missing.
   IdP updates need it.
2. **`delete(item_id)`** — DELETE to `{endpoint}/{item_id}`. The client's
   `disassociate` (`:284`) already issues a bare DELETE against a path, but the
   model-level `disassociate` (`:381`) only builds nested association paths.
   Deleting an IdP outright needs the flat form. Implemented as a client-level
   `delete(endpoint)` that `disassociate` now delegates to, so there is one
   bare-DELETE implementation rather than two.
3. **`import_config(payload)`** — POST to
   `identity-provider/import-config`, returning the raw `dict` Keycloak
   responds with. `create` (`:222`) cannot serve this: it coerces the response
   into a representation class, and `import-config` returns a flat config map,
   not an `IdentityProviderRepresentation`.

   Shipped as a **module-level `import_identity_provider_config()`**, not a
   `KeycloakAdminModel` method. `import-config` is a *sibling* of
   `identity-provider/instances`, not an operation on one, so hanging it off a
   model would mean a model whose `endpoint` attribute is a lie. It takes
   `from_url` or `metadata`, and covers both transports (see 5).

4. **`create(data)` on the model, backed by a client-level
   `create_returning_id(endpoint, data)`.** The spec's saga said to create the
   Keycloak organization "via `KeycloakAdminModel.create`". There was no such
   method — and more importantly, the client's `create` could not have backed
   one. Both creates this API makes answer **201 with an empty body**:

   | Call | Response |
   | --- | --- |
   | `POST organizations` | 201, no body, `Location` header |
   | `POST identity-provider/instances` | 201, no body, `Location` header; 409 on alias conflict |

   `create` does `representation(**response.json())`, so there is nothing to
   parse. The new id is recoverable only from the `Location` header, which is
   what `create_returning_id` reads. The saga additionally falls back to a
   lookup by alias when Keycloak sends no `Location`, because it cannot proceed
   without the organization UUID for `sso_organization_id`.

5. **`post_raw(endpoint, data)` and `post_file(endpoint, data, files)`** on the
   client. The first returns the decoded body uncoerced, for `import-config`'s
   flat config map. The second covers `import-config`'s multipart form: it
   accepts *either* a JSON body naming a URL for Keycloak to fetch **or** an
   uploaded metadata document, and the spec's `metadata_xml` input needs the
   second.

6. **`list_all(page_size=100)`** — pages on `first`/`max` until a short page
   comes back. This one is a bug fix, not an addition; see
   [Paging is not optional](#paging-is-not-optional) below.

Prefer Keycloak's own `identity-provider/import-config` over porting
`ol-infrastructure`'s `saml_helpers` into mitxonline. It accepts either
`fromUrl` or an uploaded file, parses SAML metadata server-side, and hands back
the config dict ready to attach to an IdP. It is gated on
`manage-identity-providers`, not `view-identity-providers`.

Two more response shapes worth knowing before adding Keycloak calls, both
confirmed against the published OpenAPI spec that generated
`keycloak_admin_dataclasses.py`:

- **`PUT organizations/{id}` replaces rather than merges.** Updating one field
  means reading the current representation, applying the change, and writing
  the whole thing back. `update_organization` does exactly that.
- **`POST organizations/{org-id}/identity-providers` takes a plain string body**
  (the alias) and answers 204 — which is precisely the existing `associate()`
  shape, as this spec predicted. `DELETE .../{alias}` answers 204 and matches
  `disassociate()`.

### Paging is not optional

Keycloak's collection endpoints declare `max` with `@DefaultValue("10")`. A GET
that omits it returns **at most 10 items**, with no error and no indication
that anything was cut off.

`KeycloakAdminModel.list()` passes no `max`. `reconcile_keycloak_orgs()`
(`b2b/api.py`) called `org_model.list()` with no arguments at all, and the
Production realm holds 24 organizations — so the reconciler has been
reconciling a first page rather than the realm. That is a pre-existing bug this
work surfaced, not one it introduced, and mitodl/mitxonline#3932 fixes it.

The rule this leaves behind: **any Keycloak call whose correctness depends on
seeing the whole collection must page.** That covers the realm-wide alias
checks below as much as it covers the reconciler — an alias guard that reads 10
of 24 organizations is worse than no guard, because it reads as one.

## Data model

Three additions, one migration.

### `OrganizationOnboarding`

The missing system of record: where a given customer is in the onboarding
sequence. One row per organization.

```python
class OrganizationOnboarding(TimestampedModel):
    organization = models.OneToOneField(
        OrganizationPage, on_delete=models.CASCADE, related_name="onboarding"
    )
    state = models.CharField(max_length=32, choices=ONBOARDING_STATE_CHOICES)
    state_changed_at = models.DateTimeField(default=now_in_utc)
    notes = models.TextField(blank=True, default="")
```

`state_changed_at` is stamped explicitly by `set_state()` rather than being
`auto_now`, which this spec originally called for. `auto_now` moves the field
whenever *anything* on the row is saved, so editing `notes` would look like a
state change — and the field is named for what it is supposed to record.
`TimestampedModel` supplies `created_on`/`updated_on` for the "when did this row
last change at all" question, which is the one `auto_now` actually answers.

States, in order: `requested` → `org_created` → `idp_configured` →
`idp_validated` → `contract_ready` → `live`. Plus `blocked`, reachable from
anywhere, with the reason in `notes`.

The state is descriptive, not enforcing. It records what has been observed to
be true so that a human can answer "what is left for this customer" without
reading four systems. Do not gate API calls on it in phase 1 — a state machine
that blocks operators before the operators trust it is a state machine they
work around.

### `OrganizationIdentityProvider`

MITx Online's record of an IdP it provisioned, and the lifecycle state Keycloak
has no field for.

```python
class OrganizationIdentityProvider(TimestampedModel):
    organization = models.ForeignKey(
        OrganizationPage, on_delete=models.CASCADE, related_name="identity_providers"
    )
    alias = models.CharField(max_length=255, unique=True)
    protocol = models.CharField(max_length=8, choices=IDP_PROTOCOL_CHOICES)
    lifecycle_state = models.CharField(max_length=16, choices=IDP_LIFECYCLE_CHOICES)
    display_name = models.CharField(max_length=255, blank=True, default="")
    internal_id = models.CharField(max_length=255, blank=True, default="")
    metadata_source = models.TextField(blank=True, default="")
    metadata_artifact = models.JSONField(null=True, blank=True)
    metadata_fetched_at = models.DateTimeField(null=True, blank=True)
```

`internal_id` holds Keycloak's `internalId`, which responses return alongside
our own fields. `display_name` is stored so a list response does not need a
Keycloak round trip per row.

Lifecycle: `draft` → `testing` → `active` → `disabled`. The state maps onto
Keycloak's own `enabled` and `hideOnLogin` fields rather than living only in
our database:

| State | Keycloak `enabled` | Keycloak `hideOnLogin` | Reachable by |
| --- | --- | --- | --- |
| `draft` | `false` | `true` | nobody |
| `testing` | `true` | `true` | `kc_idp_hint=<alias>` only |
| `active` | `true` | `true` | `kc_idp_hint` and email-domain org redirect |
| `disabled` | `false` | `true` | nobody |

`hideOnLogin` stays `true` throughout, matching what the Pulumi resources set
today: partner IdPs are reached by organization/domain routing or an explicit
hint, never by a button on the shared login page.

Note what that table does *not* say: `testing` and `active` carry **identical**
Keycloak flags. The difference between them is whether the organization has an
email-domain redirect pointing at the IdP, which is org-level config rather
than anything on the IdP. `transition/` moves our row and the two Keycloak
flags; it does not add or remove the domain redirect.

The allowed moves, in full:

| From | To |
| --- | --- |
| `draft` | `testing` |
| `testing` | `draft`, `active`, `disabled` |
| `active` | `testing`, `disabled` |
| `disabled` | `testing`, `active` |

There is no `draft` → `active` edge: an IdP goes live only after somebody has
actually logged in through it. `disabled` → `active` *is* allowed, because an
IdP in that state has already been through `testing` — the rule is "no
untested IdP goes live", not "everything re-enters through testing".

### Metadata artifact

`metadata_artifact` stores the parsed config dict `import-config` returned, and
`metadata_source` the URL or inline XML it came from. This is the direct fix
for the failure mode that
[ol-infrastructure#5729](https://github.com/mitodl/ol-infrastructure/pull/5729)
converts from silent to loud: with the fetched result persisted, a partner's
metadata endpoint being unreachable can neither destroy config nor block a
deploy. Refresh is an explicit operation, never a side effect of an unrelated
change.

**The artifact holds parsed metadata and nothing else.** For OIDC, `clientId`
and `clientSecret` are merged into the config sent to Keycloak but are
deliberately *not* written to `metadata_artifact`, because this field is served
back over the API. Keeping the credential out of the stored artifact is what
lets the field be returned at all.

## API surface

Namespace: `/api/v0/b2b/provisioning/`. Router registration goes in
`b2b/views/v0/urls.py` next to the existing `organizations` and `contracts`
routes; views in a new `b2b/views/v0/provisioning.py`; serializers in
`b2b/serializers/v0/provisioning.py`.

**Permissions.** `IsAdminOrReadOnly` (`main/permissions.py:26`) already grants
write access to `is_staff` and read to any authenticated user, which is exactly
the phase-1 posture. Use it directly rather than writing a new class.
`b2b/permissions.py`'s `IsOrganizationManager` is for the manager dashboard and
is not the right check here — an org manager is a customer-side role and must
not be able to provision. When C2 arrives, the partner-facing surface gets its
own permission class scoped by invite token, and this staff surface stays as it
is.

### Organizations

```
POST   /api/v0/b2b/provisioning/organizations/
GET    /api/v0/b2b/provisioning/organizations/{org_key}/
PATCH  /api/v0/b2b/provisioning/organizations/{org_key}/
POST   /api/v0/b2b/provisioning/organizations/{org_key}/onboarding/
```

`onboarding/` takes `{"state": ..., "notes": ...}` and is not in the original
spec. It has to exist: the onboarding row is only ever written once, at
`org_created`, so without a mover the "system of record" is a field that never
changes and cannot answer the question it was added for. It remains
descriptive — nothing in this API gates on the state it records.

`POST` body:

```json
{
  "name": "Example University",
  "org_key": "EXAMPLEU",
  "org_key_prefix": "UAI_",
  "domains": ["example.edu"],
  "description": "",
  "redirect_url": "https://learn.mit.edu/dashboard/organization/exampleu"
}
```

`org_key` is required on create and immutable afterwards.
`create_contract_run_key()` builds every B2B courseware ID as
`course-v1:{org_key_prefix}{org_key}+{course}+{run_tag}` (`b2b/api.py:312`),
which is why `reconcile_single_keycloak_org` deliberately refuses to update
`org_key` on subsequent syncs (`b2b/api.py:1768`). The API must reject an
`org_key` change with a 400 rather than accept and ignore it. Note the same
function bakes the contract's database primary key into the run tag
(`B2B_RUN_TAG_FORMAT`, `b2b/api.py:336`), so contracts cannot be pre-created
out of band either — relevant to the phase-2 contract saga, not to phase 1.

`GET` returns our record plus `domains` and `redirect_url` read back from
Keycloak, because those two live *only* there. Reporting what we asked for
rather than what is present would defeat the point of a provisioning API. The
cost is one admin API call per detail read, and a Keycloak failure surfaces as
502 rather than a stale-looking 200.

`PATCH` accepts `name`, `description`, `redirect_url` and `domains`. Domain
changes are the interesting case: today every domain Pulumi declares is written
with `verified=True` with no verification having occurred
(`org_sso_helpers.py:115` in ol-infrastructure). A partner asserting a domain
they do not control is currently accepted on trust.

Phase 1 preserves that behaviour — staff assert domains — and records the
assertion, which is defensible only while the asserting party is MIT staff. It
stops being defensible the moment C2 lets a partner assert their own domain, so
DNS-TXT or email verification is a **precondition of C2, not a later
enhancement**. Model the field now so that work is a fill-in rather than a
migration.

### Identity providers

```
POST   /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/
GET    /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/
GET    /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/{alias}/
PATCH  /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/{alias}/
DELETE /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/{alias}/
POST   /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/{alias}/refresh-metadata/
POST   /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/{alias}/transition/
POST   /api/v0/b2b/provisioning/parse-metadata/
```

`parse-metadata` is deliberately unnested and creates nothing. It proxies
`import-config` so an operator (later, a wizard) can paste a metadata URL or
XML blob and see what Keycloak makes of it before committing to a resource.
This is the single most useful endpoint for the eventual wizard and the
cheapest to build.

`POST identity-providers/` body, SAML:

```json
{
  "protocol": "saml",
  "alias": "exampleu",
  "display_name": "Example University",
  "metadata_url": "https://idp.example.edu/metadata.xml",
  "attribute_map": {"email": "E-Mail Address"}
}
```

OIDC takes `discovery_url`, `client_id` and `client_secret` in place of
`metadata_url`. Either protocol may supply `metadata_xml` instead of a URL.

`transition/` takes `{"state": "testing"}` and is the only way the lifecycle
state moves. It writes both our row and the corresponding Keycloak `enabled`
flag in one operation, so the two cannot drift silently. Reject transitions
that skip `testing`: an IdP goes live only after somebody has actually logged
in through it.

Response bodies return our `OrganizationIdentityProvider` fields plus the
Keycloak `internalId`, never the client secret.

### What phase 1 does not expose

No contract endpoints. Contract creation stays on `b2b_contract create` until
the phase-2 saga (mitodl/hq#12784, capability C3) replaces the command
sequence. No enrollment-code endpoints, no manager designation — C4 handles
manager designation through Keycloak Organization Groups (mitodl/hq#10594) and
this API should not grow a second way to do it.

## What comes after, and what gates what

The RFC labels five capabilities, and the shorthand gets used as though it were
self-evident. It is not: **C1** is this provisioning API, **C2** the
partner-facing self-service SSO wizard, **C3** the contract orchestration saga,
**C4** manager designation via Keycloak Organization Groups, **C5** entitlement
automation. The phases interleave them rather than mapping one-to-one — phase 2
is C3 *plus* a staff UI, and that staff UI has no capability letter of its own.

Two sequencing decisions were made on 2026-09-03 that this API's consumers
depend on:

**The phase-2 staff UI gates deprecating the Pulumi path.** This API gives MITx
Online the capability to provision organizations and IdPs, but an API is not an
operational replacement for a process — someone has to drive it. Today a partner
is onboarded by a reviewed PR against `olapps.py`, and that is the live path, not
a legacy one. The Pulumi creation path is not retired until operators have a
usable surface over this API.

**The staff UI also ships before the C2 partner wizard,** so the staff surface
proves out this API and the IdP lifecycle before the same machinery is exposed
outside MIT. Two reasons that ordering is load-bearing: a bug in the staff UI is
caught by an operator who knows the system, whereas the same bug in the wizard is
hit by a partner engineer mid-onboarding; and the wizard is strictly a superset
of the staff surface — the same calls plus identity, domain verification and an
approval gate — so anything wrong underneath is cheaper to find on the smaller
one.

Neither decision changes phase 1's scope. Both are recorded here because they
determine what this API has to be *good enough for* before anything else moves.

## The organization creation saga

`POST /organizations/` writes to two systems. The ordering is what makes it
safe:

1. Validate. Reject a duplicate `org_key` (the field is `unique=True`,
   `b2b/models.py:108`) and a duplicate Keycloak alias before writing anything.
   The alias check must query the **realm**, not just `OrganizationPage`:
   aliases are realm-wide and shared with the organizations Pulumi still
   declares, so a name that is free in our database can still collide. It must
   also *page* the realm — see [Paging is not optional](#paging-is-not-optional).
2. Create the Keycloak organization with its domains, via
   `KeycloakAdminModel.create` on the `organizations` endpoint. This is the
   step that can fail for reasons outside our control, so it goes first.
   Keycloak answers 201 with an empty body, so the new UUID comes from the
   `Location` header, with a lookup by alias as the fallback — the saga cannot
   continue without it.
3. In a single `transaction.atomic()` block, create the `OrganizationPage`
   under `OrganizationIndexPage` with `sso_organization_id` set to the UUID
   Keycloak just returned, and the `OrganizationOnboarding` row in state
   `org_created`.
4. If step 3 raises, delete the Keycloak organization created in step 2 and
   re-raise. A Keycloak org with no MITx Online counterpart is the failure this
   compensation exists to prevent; it is precisely the shape of the orphan
   problem described below.

Keycloak has no transactions, so step 4 is a compensating action rather than a
rollback, and it can itself fail. When it does, log the orphaned organization
ID at `error` and leave the Keycloak org in place — `reconcile_keycloak_orgs()`
will adopt it on its next run, which is the correct outcome and better than a
retry loop against a system that just failed.

That fallback is only real because `reconcile_keycloak_orgs()` now pages. While
it was reading a first page of 10, an orphan sitting past the boundary would
never have been adopted and this paragraph would have been describing a
recovery that could not happen.

Step 3 adds the page under `OrganizationIndexPage.objects.first()`, matching
what the reconciler does, rather than calling `ensure_b2b_organization_index()`.
The latter *moves every existing organization page* when its child count and
`OrganizationPage.objects.count()` disagree (`b2b/api.py:127`), which is not an
acceptable side effect of creating one organization.

An `OrganizationPage` must never be created without `sso_organization_id`. The
existing `b2b_contract create --create` path does exactly that
(`b2b/management/commands/b2b_contract.py:296`), and orgs in that state are
silently broken: `attach_user()` returns `False` without doing anything
(`b2b/models.py:176`), so every membership write is a no-op. Once this API
exists, `--create` should be removed rather than fixed — there is no reason to
keep a second, worse org-creation path.

Removed in mitodl/mitxonline#3932, along with the `--org-key` argument that only
existed to feed it; the command's error now points at
`POST /api/v0/b2b/provisioning/organizations/`. `b2b_contract import`'s
`_import_organization` is deliberately untouched: it is a separate declarative
path that carries `sso_organization_id` through from the export, so it does not
mint the broken shape.

## Demoting `sync_keycloak_orgs` to self-heal

`reconcile_keycloak_orgs()` (`b2b/api.py:1777`) is currently the only way a
Keycloak organization becomes an `OrganizationPage`. After C1 it becomes a
reconciler for drift, not the primary path:

- Keep it running on its schedule. It is how organizations created outside the
  API — by the compensation failure above, by console work, by the orgs Pulumi
  still owns mid-migration — get adopted.
- Keep `org_key` immutable on adoption (`b2b/api.py:1768`). That behaviour is
  load-bearing for courseware IDs, not an oversight.
- Add: when it adopts an organization that has no `OrganizationOnboarding` row,
  create one in state `org_created` so adopted orgs are visible in the same
  place as provisioned ones.
- **Fix: switch it from `list()` to `list_all()`.** This was not in the original
  spec because the bug had not been found yet. `list()` sends no `max`, so
  Keycloak caps the response at 10; Production has 24 organizations. The
  reconciler has therefore been reconciling a fraction of the realm for as long
  as it has existed, which is also why the "adopted on the next run" fallback
  for a failed compensation could not be relied on. Fixed in
  mitodl/mitxonline#3932.
- Consider dropping `KEYCLOAK_ORG_SYNC_FREQUENCY` well below 86400 once it is
  no longer the primary create path. A self-heal loop that runs daily is a
  self-heal loop that hides a problem for a day. This is a config change, not
  code, and can wait for evidence of actual drift. Not done in phase 1.

The truncation is worth generalising rather than treating as one bad call: it
is silent, it grows with the customer base, and every one of this API's
realm-wide guards has the same exposure. It is recorded outside this document
so other Keycloak consumers (`ol-keycloak`, `ol-infrastructure`) inherit it.

## Migration and data debt

**Pulumi handover.** Per-org Keycloak resources — organizations, domains, IdPs,
mappers — must leave Pulumi state without being deleted from Keycloak. That is
`retain_on_delete` plus state surgery, sequenced so the API can manage the
existing resources before Pulumi stops declaring them. Tracked as
`tk-migrate-per-org-keycloak-resources-out-of-pulumi-632a53`.

This is **not** a phase-1 prerequisite — see the ownership boundary above for
why an organization created through this API is invisible to Pulumi and safe.
What does hold: do not *modify* an organization that Pulumi still declares. The
next `pulumi up` reverts whatever the API wrote.

Two risks belong to that task and are noted here because they shape when it can
start:

- **There is no rehearsal environment.** Every real partner org sits behind
  `if stack_info.env_suffix == "production":` (`olapps.py:917`); CI and QA have
  only `moira` and `company-x`, neither with an IdP. The state-surgery sequence
  cannot be practiced anywhere, so the first real execution would be against
  production partner SSO. A throwaway QA partner org is tracked separately as
  the fix.
- **The handover removes the review gate.** A partner's SSO config currently
  changes only through a reviewed, merged PR. Afterwards it is an API call. For
  SSO federation that is a real loss of control, and the staff UI is where it has
  to be won back — an audit trail of who changed which partner's IdP and when, at
  minimum. This API should emit what that trail needs from the start rather than
  having it retrofitted.

**Orphaned organizations.** As of April 2026 there were roughly 24
`OrganizationPage` records with a null `sso_organization_id`, inherited from
mitodl/hq#10552. That count is unverified since, and re-counting it against
production is step one. Those orgs need Keycloak organizations created through
this API and a one-off membership reconciliation. Tracked as
`tk-backfill-mitx-online-orgs-with-no-keycloak-count-ca1e06`.

## Idempotency and failure modes

Every write endpoint must be safe to retry, because the operator's first
instinct on a 500 is to run it again.

- Creating an organization whose `org_key` or Keycloak alias already exists
  returns 409 with the existing resource, not a duplicate.
- Creating an IdP whose alias already exists returns 409. Keycloak aliases are
  realm-wide, not per-organization, so alias collision across two customers is
  a real possibility and must be caught before the create call.
- `refresh-metadata` on an unreachable endpoint returns 502 and leaves the
  stored artifact untouched. It never clears the artifact — that is the whole
  point of storing it.
- A Keycloak call that fails after our row is written leaves the row in place
  with its previous lifecycle state and returns 502. Our row lagging Keycloak
  is recoverable; a deleted partner integration is not.

As built, that comes out as:

| Condition | Status |
| --- | --- |
| Alias taken here or in the realm | 409 |
| `org_key` change attempted on `PATCH` | 400 |
| Lifecycle transition that skips `testing` | 400 |
| Compensating delete also failed (orphan) | 500, with the orphan ID in the detail |
| Any Keycloak admin call failed | 502 |

502 rather than 500 for Keycloak failures is the load-bearing one: our records
are intact and the operator's next move is to retry, not to open a ticket
against MITx Online. It is implemented as a `handle_exception` override on a
mixin shared by all three viewsets, so no endpoint can forget it.

## Testing

- Unit tests against a mocked `KeycloakAdminClient` for the saga's happy path,
  the step-3-fails compensation, and the compensation-also-fails path. The
  existing `b2b/keycloak_admin_api_test.py` establishes the mocking approach.
- A test asserting `org_key` cannot be changed through `PATCH`.
- A test asserting `POST /organizations/` never produces an `OrganizationPage`
  with a null `sso_organization_id`, including when the Keycloak call fails.
- Lifecycle transition tests, including the rejected `draft` → `active` skip.
- ~~Against the QA realm, confirm the service account can reach the IdP
  endpoints.~~ Done 2026-09-03; results in the service-account section above.
  Re-run it against **production** credentials before the handover, since only
  QA has been exercised.

All of the above is written, in `b2b/provisioning_test.py` (20 tests) and
`b2b/views/v0/provisioning_test.py` (15). Three cases were added that this list
did not anticipate, each guarding a decision made during implementation:

- the OIDC client secret reaches Keycloak but does not appear in the stored
  `metadata_artifact`;
- `list_all` issues the exact `first`/`max` sequence, since the truncation it
  exists to prevent is silent and a wrong page size would be too;
- a plain authenticated user gets 403 on both `POST /organizations/` and
  `parse-metadata/`, which is the boundary between this API and C2.

## OpenAPI

`manage.py generate_openapi_spec` regenerates `openapi/specs/v{0,1,2}.yaml`
purely additively — no component is renamed or removed — and warning-free.

Getting there needed three `ENUM_NAME_OVERRIDES` entries in
`openapi/settings_spectacular.py`, one of which is not about this API at all:
**`StateEnum` is pinned to `ecommerce.models.OrderStatus`**. Adding `state`
fields here collides with ecommerce's existing one, and drf-spectacular resolves
a collision by renaming the *published* component to a hashed name
(`State402Enum`) — unstable across regenerations and a breaking rename for
anything generated from the spec. Any future work that adds another `state`
field should expect to pin it the same way.

## Decisions

1. **Alias naming — settled.** The Keycloak **organization** alias is `org_key`
   verbatim. The **IdP** alias stays operator-chosen with realm collision
   rejection.

   The organization half turned out not to be a judgement call.
   `reconcile_single_keycloak_org` sets `org_key = keycloak_org.alias[:30]` when
   it adopts an organization (`b2b/api.py`), so any alias that is not the
   `org_key` gives an adopted organization a *different* `org_key` from the one
   it was created with — and `org_key` is in every B2B courseware ID. Since the
   compensation-failure path deliberately routes orgs through that adoption, the
   round trip has to be lossless. A partner with two IdPs still needs a suffix
   scheme, which is why the IdP half stays operator-chosen.

   The **collision guard is not optional** either way. Aliases are shared with
   the resources Pulumi still declares, so an alias this API creates will break
   a later `pulumi up` that declares the same name. Check the realm, not just
   our own tables, before creating — and page it.

2. **Where the invite token for C2 lives — still open.** Phase 1 does not need
   it, but the `OrganizationOnboarding` row is the obvious home, and deciding
   now avoids a second migration. Not decided by this work; migration 0028 does
   not carry a token field.

3. **Whether `parse-metadata` should be reachable by an org manager.** It
   creates nothing and leaks nothing about other customers, so it is the one
   endpoint that could safely move to the customer side early. It is also the
   endpoint most likely to be abused as an SSRF probe, since it makes the
   server fetch an operator-supplied URL — and that egress is confirmed
   working, not theoretical: QA Keycloak fetched an arbitrary external HTTPS
   host through `import-config` on 2026-09-03. Keep it staff-only in phase 1.
   Exposing it to partners needs an allowlist or deny-private-ranges policy and
   a rate limit, which belongs to C2's threat model.

   Shipped staff-only, with a test asserting a non-staff authenticated user gets
   403. The question itself is still C2's to answer.
