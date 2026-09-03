# B2B Provisioning API (C1) — implementation spec

Status: spec, not yet implemented.
Design RFC: <https://github.com/mitodl/hq/discussions/12784>

This is the phase-1 implementation spec for the runtime provisioning API that
takes ownership of per-customer Keycloak resources from Pulumi. It is a
staff-only API surface; the partner-facing self-service wizard (C2) is a later
UI built on top of it and is out of scope here.

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

`KeycloakAdminModel` needs three additions before the IdP endpoints can be
written. All three belong in `b2b/keycloak_admin_api.py` alongside the existing
methods.

1. **`update(item_id, data)`** — PUT to `{endpoint}/{item_id}`. `save` on the
   client takes a full URL path, so the model-level convenience is missing.
   IdP updates need it.
2. **`delete(item_id)`** — DELETE to `{endpoint}/{item_id}`. The client's
   `disassociate` (`:284`) already issues a bare DELETE against a path, but the
   model-level `disassociate` (`:381`) only builds nested association paths.
   Deleting an IdP outright needs the flat form.
3. **`import_config(payload)`** — POST to
   `identity-provider/import-config`, returning the raw `dict` Keycloak
   responds with. `create` (`:222`) cannot serve this: it coerces the response
   into a representation class, and `import-config` returns a flat config map,
   not an `IdentityProviderRepresentation`.

Prefer Keycloak's own `identity-provider/import-config` over porting
`ol-infrastructure`'s `saml_helpers` into mitxonline. It accepts either
`fromUrl` or an uploaded file, parses SAML metadata server-side, and hands back
the config dict ready to attach to an IdP. It is gated on
`manage-identity-providers`, not `view-identity-providers`.

## Data model

Three additions, one migration.

### `OrganizationOnboarding`

The missing system of record: where a given customer is in the onboarding
sequence. One row per organization.

```python
class OrganizationOnboarding(models.Model):
    organization = models.OneToOneField(
        OrganizationPage, on_delete=models.CASCADE, related_name="onboarding"
    )
    state = models.CharField(max_length=32, choices=ONBOARDING_STATE_CHOICES)
    state_changed_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
```

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
class OrganizationIdentityProvider(models.Model):
    organization = models.ForeignKey(
        OrganizationPage, on_delete=models.CASCADE, related_name="identity_providers"
    )
    alias = models.CharField(max_length=255, unique=True)
    protocol = models.CharField(max_length=8, choices=[("saml", "SAML"), ("oidc", "OIDC")])
    lifecycle_state = models.CharField(max_length=16, choices=IDP_LIFECYCLE_CHOICES)
    metadata_source = models.TextField(blank=True)
    metadata_artifact = models.JSONField(null=True, blank=True)
    metadata_fetched_at = models.DateTimeField(null=True, blank=True)
```

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

### Metadata artifact

`metadata_artifact` stores the parsed config dict `import-config` returned, and
`metadata_source` the URL or inline XML it came from. This is the direct fix
for the failure mode that
[ol-infrastructure#5729](https://github.com/mitodl/ol-infrastructure/pull/5729)
converts from silent to loud: with the fetched result persisted, a partner's
metadata endpoint being unreachable can neither destroy config nor block a
deploy. Refresh is an explicit operation, never a side effect of an unrelated
change.

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
```

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
   declares, so a name that is free in our database can still collide.
2. Create the Keycloak organization with its domains, via
   `KeycloakAdminModel.create` on the `organizations` endpoint. This is the
   step that can fail for reasons outside our control, so it goes first.
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

An `OrganizationPage` must never be created without `sso_organization_id`. The
existing `b2b_contract create --create` path does exactly that
(`b2b/management/commands/b2b_contract.py:296`), and orgs in that state are
silently broken: `attach_user()` returns `False` without doing anything
(`b2b/models.py:176`), so every membership write is a no-op. Once this API
exists, `--create` should be removed rather than fixed — there is no reason to
keep a second, worse org-creation path.

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
- Consider dropping `KEYCLOAK_ORG_SYNC_FREQUENCY` well below 86400 once it is
  no longer the primary create path. A self-heal loop that runs daily is a
  self-heal loop that hides a problem for a day. This is a config change, not
  code, and can wait for evidence of actual drift.

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

## Open decisions

1. **Alias naming.** Keycloak organization and IdP aliases are realm-wide.
   Derive from `org_key` (collision-free by construction, since `org_key` is
   unique) or let the operator choose and reject collisions? Deriving is safer;
   a partner with two IdPs needs a suffix scheme either way.

   Whichever is chosen, the **collision guard is not optional**. Aliases are
   shared with the resources Pulumi still declares, so an alias this API creates
   will break a later `pulumi up` that declares the same name. Check the realm,
   not just our own tables, before creating.

2. **Where the invite token for C2 lives.** Phase 1 does not need it, but the
   `OrganizationOnboarding` row is the obvious home, and deciding now avoids a
   second migration.

3. **Whether `parse-metadata` should be reachable by an org manager.** It
   creates nothing and leaks nothing about other customers, so it is the one
   endpoint that could safely move to the customer side early. It is also the
   endpoint most likely to be abused as an SSRF probe, since it makes the
   server fetch an operator-supplied URL — and that egress is confirmed
   working, not theoretical: QA Keycloak fetched an arbitrary external HTTPS
   host through `import-config` on 2026-09-03. Keep it staff-only in phase 1.
   Exposing it to partners needs an allowlist or deny-private-ranges policy and
   a rate limit, which belongs to C2's threat model.
