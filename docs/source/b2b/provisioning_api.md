# Provisioning API

The provisioning API is how MIT staff set up a B2B customer: the Keycloak
organization, its identity provider (IdP), and the contracts that give its
members access to courseware. It lives under `/api/v0/b2b/provisioning/` and is
staff-only.

Most people will use it through the staff dashboard's B2B Organizations
section, which covers organizations, onboarding state, IdPs and the change
history. Contracts don't have a staff UI yet and are still edited in Wagtail,
as child pages of the organization, or through the contract routes below. This
page is the reference for engineers working on the API or the UI, and for
anyone who needs to know what a button in the dashboard actually does.

The design came from the B2B onboarding RFC,
<https://github.com/mitodl/hq/discussions/12784>. It uses a few labels from
that RFC: C1 is this API's organization and IdP routes, C2 is a future
partner-facing self-service SSO wizard, C3 is contract setup, and C4 is manager
designation through Keycloak organization groups.

## What it owns

Before this API, a new customer's Keycloak resources were declared in a Pulumi
PR against `ol-infrastructure`'s `olapps.py`. The MITx Online
`OrganizationPage` only appeared once `reconcile_keycloak_orgs()` next ran,
which is up to `KEYCLOAK_ORG_SYNC_FREQUENCY` (24 hours by default) later.

Keycloak ownership is now split:

- Pulumi keeps the realm, authentication flows, client scopes, clients and
  service-account role grants.
- This API owns Keycloak organizations, their domains, IdPs, IdP attribute
  mappers and org-to-IdP links, along with the MITx Online records that go with
  them (`OrganizationPage`, `OrganizationOnboarding`,
  `OrganizationIdentityProvider`, `ContractPage`).

Pulumi only deletes resources that are in its own state, so an organization
created here is invisible to it and won't be removed by a `pulumi up`. The
hazard between the two systems is alias collision. Organization and IdP
aliases are realm-wide, and an alias this API claims will fail a later Pulumi
deploy that declares the same name. Every create checks the whole realm
(paging through it, since Keycloak returns only 10 items when no page size is
given) and returns 409 if the alias is taken.

The organizations Pulumi already declares are still Pulumi's. Don't modify one
of them through this API; the next `pulumi up` will revert the change.

## Organizations

```
GET    /api/v0/b2b/provisioning/organizations/
POST   /api/v0/b2b/provisioning/organizations/
GET    /api/v0/b2b/provisioning/organizations/{org_key}/
PATCH  /api/v0/b2b/provisioning/organizations/{org_key}/
POST   /api/v0/b2b/provisioning/organizations/{org_key}/onboarding/
GET    /api/v0/b2b/provisioning/organizations/{org_key}/events/
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

Creating an organization writes to Keycloak first, then creates the
`OrganizationPage` and its onboarding record in one database transaction. If
the database write fails, the Keycloak organization is deleted again. If that
delete also fails, the API returns 500 naming the orphaned Keycloak
organization, and the reconciler adopts the organization on its next run.

The Keycloak alias is the `org_key`. This matters because the reconciler
derives `org_key` from the alias when it adopts an organization, and `org_key`
is part of every B2B courseware ID (`course-v1:{org_key_prefix}{org_key}+...`).
For the same reason `org_key` can't be changed after creation, and a `PATCH`
that includes it gets a 400.

`PATCH` accepts `name`, `description`, `redirect_url` and `domains`. `domains`
replaces the whole list.

Domains are written to Keycloak as verified, with no verification step. That's
acceptable while MIT staff are the ones asserting domains. It won't be once C2
lets a partner assert their own, so domain verification (DNS TXT or email) has
to exist before C2 ships.

`domains` and `redirect_url` are stored only in Keycloak. The detail response
reads them back from Keycloak on every request, so it shows what's actually
configured. The list response doesn't make a Keycloak call per row, so those
two fields are null there. The list filters on `q` (name or org key) and
`onboarding_state`.

### Onboarding state

Each organization has one `OrganizationOnboarding` record answering "how far
along is this customer". The states, in order: `requested`, `org_created`,
`idp_configured`, `idp_validated`, `contract_ready`, `live`. `blocked` can be
set from any state, with the reason in `notes`.

The state is descriptive. Staff set it with `POST .../onboarding/`, and nothing
in the API checks it before allowing an action. Organizations created here
start at `org_created`, and so do organizations the reconciler adopts.

### Change history

Every change made through the provisioning functions writes an
`OrganizationProvisioningAudit` row in the same transaction: organization
create and update, onboarding changes, and IdP create, update, transition,
metadata refresh and delete. Each row records who made the change and the data before
and after it. `GET .../events/` returns them newest first.

Partner SSO changes used to go through PR review in Pulumi. We decided on
2026-09-18 not to add an approval step before an IdP goes active, so this
history is the control that replaces that review. OIDC client secrets are never
written to it. Contract changes aren't audited here.

## Identity providers

```
GET    /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/
POST   /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/
GET    /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/{alias}/
PATCH  /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/{alias}/
DELETE /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/{alias}/
POST   /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/{alias}/refresh-metadata/
POST   /api/v0/b2b/provisioning/organizations/{org_key}/identity-providers/{alias}/transition/
POST   /api/v0/b2b/provisioning/parse-metadata/
```

`POST` body for SAML:

```json
{
  "protocol": "saml",
  "alias": "exampleu",
  "display_name": "Example University",
  "metadata_url": "https://idp.example.edu/metadata.xml",
  "attribute_map": {"email": "mail", "firstName": "givenName"}
}
```

SAML takes exactly one of `metadata_url` or `metadata_xml`, and at least one
of `attribute_map` (matched by the attribute's FriendlyName) or
`attribute_name_map` (matched by its Name). A SAML IdP with no mappers logs
users in with no email or name. OIDC takes `discovery_url`, `client_id` and
`client_secret`; attribute mappings are optional.

Keycloak's `identity-provider/import-config` parses the metadata. The parsed
config is stored on the `OrganizationIdentityProvider` as `metadata_artifact`,
along with where it came from. Metadata is only fetched again when someone
calls `refresh-metadata`. A refresh replaces the parsed config, so a key the
partner's metadata no longer defines (e.g. a withdrawn certificate or logout
endpoint) is removed from Keycloak too. If the partner's endpoint is down, the
refresh returns 502 and the stored config is left as it was. The OIDC client secret is
sent to Keycloak but never stored in MITx Online.

`parse-metadata` runs the same parse without creating anything, so staff can
check what Keycloak reads from a partner's metadata first. It's staff-only
because the URL form makes Keycloak fetch an address the caller supplies. Any
version of it exposed to partners needs an allowlist and a rate limit.

Each IdP response includes `service_provider`: the SP entity ID, the SAML ACS
URL or OIDC redirect URI, and the SP metadata URL. These are the values to
send to the partner.

An IdP alias is chosen by staff, not derived from `org_key`, because one
organization can have more than one IdP.

### Editing an identity provider

`DELETE` on an IdP is destructive beyond this API. Keycloak's IdP delete also
deletes every user's federated identity link to that alias, so everyone who
has signed in through the IdP has to re-link on their next login. `PATCH`
exists so that rotating an OIDC client secret, pointing at new metadata or
fixing a mapper doesn't cost that.

`PATCH` takes any of these, and only the fields sent are changed:

| Field | Protocol | Notes |
| --- | --- | --- |
| `display_name` | both | The only field that may be sent blank |
| `metadata_url`, `metadata_xml` | SAML | At most one. The metadata is parsed again and replaces the stored config |
| `discovery_url` | OIDC | Parsed again, the same as SAML metadata |
| `client_id`, `client_secret` | OIDC | The secret goes to Keycloak and is never stored or audited |
| `attribute_map`, `attribute_name_map` | see below | Replace the IdP's attribute mappers |

The attribute maps replace the whole set of attribute mappers, they don't
merge into it. For SAML, send both maps together (an empty object for the one
with no entries), because sending one alone would delete the other's mappers.
A user attribute can be in only one of the two, and the pair can't leave a
SAML IdP with no mappers. OIDC takes `attribute_map` only, and an empty
object clears its mappers. Mappers of other types added in the Keycloak
console are left alone.

`alias` and `protocol` can't be changed. Sending either is a 400, and so is a
field that belongs to the other protocol or a body with no fields. The
lifecycle state doesn't change here, only through `transition/`.

The update writes the IdP to Keycloak, then replaces the mappers, then saves
the MITx Online record, with no compensation. If a step fails, Keycloak is
ahead of MITx Online, and on SAML it may have fewer mappers than it started
with. Send the same `PATCH` again to finish it.

### Lifecycle

New IdPs start in `draft`. `transition/` is the only way to change the state,
and it updates Keycloak's `enabled` and `hideOnLogin` flags in the same call,
so MITx Online and Keycloak can't disagree about it.

| State | Keycloak `enabled` | Keycloak `hideOnLogin` |
| --- | --- | --- |
| `draft` | `false` | `true` |
| `testing` | `true` | `true` |
| `active` | `true` | `true` |
| `disabled` | `false` | `true` |

`hideOnLogin` is always `true`, the same as the IdPs Pulumi manages. Partner
IdPs are reached through the organization's email-domain redirect or an
explicit `kc_idp_hint`, never through a button on the shared login page.
`testing` and `active` set the same Keycloak flags. What makes an IdP live for
users is the organization's domain routing, which is set on the organization,
not the IdP. The two states tell staff whether someone has logged in through
the IdP yet.

Allowed transitions:

| From | To |
| --- | --- |
| `draft` | `testing` |
| `testing` | `draft`, `active`, `disabled` |
| `active` | `testing`, `disabled` |
| `disabled` | `testing`, `active` |

There's no `draft` to `active` move. An IdP only goes live after someone has
logged in through it. Nothing in MITx Online passes `kc_idp_hint` through to
Keycloak yet, so testing an IdP still takes a hand-built login URL.

## Contracts

```
GET    /api/v0/b2b/provisioning/organizations/{org_key}/contracts/
POST   /api/v0/b2b/provisioning/organizations/{org_key}/contracts/
GET    /api/v0/b2b/provisioning/organizations/{org_key}/contracts/{id}/
PATCH  /api/v0/b2b/provisioning/organizations/{org_key}/contracts/{id}/
POST   .../contracts/{id}/courseware/
POST   .../contracts/{id}/courseware/remove/
GET    .../contracts/{id}/setup-status/
POST   .../contracts/{id}/retry-setup/
GET    .../contracts/{id}/codes/
POST   .../contracts/{id}/codes/expire/
POST   .../contracts/{id}/codes/assign/
GET    .../contracts/{id}/variants/
POST   .../contracts/{id}/variants/
PATCH  .../contracts/{id}/variants/{variant_id}/
```

These replace running `b2b_contract`, `b2b_courseware`, `b2b_codes` and
`check_contract_variant` by hand, using the same functions in
`b2b/contracts.py`. The management commands still work.

`POST` takes `name`, `membership_type` (required), `description`,
`welcome_message`, `contract_start`, `contract_end`, `max_learners` and
`enrollment_fixed_price`. `PATCH` takes the same fields plus `active`.

`courseware/` takes a program, course or course run readable ID. The contract
runs and their products exist once the call returns. The edX course clones and
enrollment codes are created afterwards by Celery tasks, and `setup-status`
reports what's still pending or has failed. `retry-setup` queues the failed
parts again. Adding the same courseware twice doesn't create a second run. A
run that already belongs to another contract is skipped and stays where it is.

Adding a program creates runs for each of its courses. A course with no source
run to clone (none at all, or none for the contract's variant sets) is skipped,
and the response's `courses_without_source_run` counts those courses. The rest
of the program is still added. Adding a single course with no usable source run
is a 400.

`courseware/remove/` closes the removed runs to new enrollments. A run that
already has enrolled learners stays linked to the contract so they keep access.

`variants/` lists the contract's variant sets, default first. Each set lists
the contract's courses (from its runs and its programs) that support the same
language, length and industry, whether each has a source run for it, and the
contract's run for it if there is one. A course with a source run and no
contract run gets one the next time its courseware is added to the contract.
`POST` adds a set (`language`, `variant_length`, `variant_industry`,
`b2b_only`). It never adds a default, since every contract already has one, and
a set the contract already has, active or not, is a 400. Adding a set creates
no runs. `PATCH` takes `active` and `b2b_only`. An inactive set gets no new
runs and its runs drop out of the contract's course list, but they stay in the
contract and their enrollments are untouched, so turning it back on restores
them. The default set can't be turned off or made B2B-only. Variant set changes
are recorded in the organization's change history.

The codes routes list a contract's enrollment codes, expire the unused ones,
and assign codes to people by email the same way the manager dashboard's bulk
assign does. They return redeemable codes, which is part of why every route
here requires staff, including reads.

## Errors

| Condition | Status |
| --- | --- |
| `org_key` or alias already used in MITx Online or the realm | 409 |
| Organization name gives a page slug that's already taken | 409 |
| Acting on an organization with no Keycloak organization | 409 |
| `org_key` sent on `PATCH` | 400 |
| `alias` or `protocol` sent on an IdP `PATCH` | 400 |
| Lifecycle transition not in the table above | 400 |
| Database write and compensating Keycloak delete both failed | 500 |
| A Keycloak admin API call failed | 502 |

A Keycloak failure is a 502, not a 500. MITx Online's records are unchanged,
so retrying is the right response. The "no Keycloak organization" 409 applies
to organizations created before Keycloak became the source of truth: they need
a Keycloak organization created and linked before this API can manage them.

## Reconciler

`reconcile_keycloak_orgs()` still runs on its Celery beat schedule, but it's no
longer the normal way an organization reaches MITx Online. It picks up
organizations created outside this API: the ones Pulumi still declares,
anything created in the Keycloak console, and any organization left behind by
a failed compensating delete. It pages through the whole realm and never
changes an existing `org_key`.

## Still open

- Pulumi handover. The per-organization resources Pulumi already declares
  need to be moved out of Pulumi state without deleting them from Keycloak.
- Orphaned organizations. As of April 2026, about 24 `OrganizationPage`
  records from before Keycloak was the source of truth had no
  `sso_organization_id` (mitodl/hq#10552). They need Keycloak organizations created and their
  memberships reconciled.
- Domain verification, before C2.
- Where C2's partner invite token is stored. `OrganizationOnboarding` is the
  likely place, but it has no token field yet.
- A contracts section in the staff dashboard, an IdP edit form over the
  `PATCH` route, and a test-login flow.
