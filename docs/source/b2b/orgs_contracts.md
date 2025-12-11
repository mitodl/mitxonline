# Organizations and Contracts

Organizations and contracts are the core data for the B2B system.

## Organizations

Organizations are the root - they represent a particular organization or institution that we are partering with to provide content. Organizations exist in both MITx Online and in Keycloak, and records in MITx Online and Keycloak are closely coupled.

Within MITx Online, Organizations are pretty simple. We keep track of some basic metadata - name, logo, description, etc. We also store an identifier for the corresponding record in Keycloak.

Keycloak Organizations contain some of the same basic metadata. But, they also contain information about any connected identity providers that the organization might have. If an identity provider is configured, learners that belong to the organization can log in using their organization's login process and credentials, and they will be automatically identified by Keycloak as members of the organization. Keycloak matches new users to organizations based on their email address - a new user logging as with `profx@mit.edu`, for instance, is identified as being part of the MIT organization, and is redirected through Touchstone rather than being prompted to set up an account.

Both MITx Online and Keycloak keep track of learners' organization memberships. However, MITx Online keeps track of it more as a cache; it trusts Keycloak's determination of the learner's organization membership. We can override this if necessary, but only temporarily.

### Edge cases

Organizations in MITx Online should always link to a Keycloak organization. There are some cases where this isn't the case, however. If the organization was created before we had the sync code in, the organization may only exist in MITx Online. If we want to do local testing with an org, we may also opt to have an org that's not connected to Keycloak.

Organizations that were created before we made Keycloak the authoritative source of truth should ideally be set up in Keycloak.

## Contracts

Contracts are the next level up from Organizations. Contracts connect learners to organizations and to courseware resources. They define what resources are available to members, and they define how learners attain membership. Organizations can have any number of contracts.

### Membership

Contracts contain a number of data elements that control membership:

- `membership_type`/`integration_type` - determines how learners gain access specifically.
- `max_learners` - controls how many learners can be attached to the contract.
- `price` - controls whether or not the learners are assessed a fee for access to courses.

:::{note}
The membership_type and integration_type fields are very similar, because one will be removed. `integration_type` was the old name, and `membership_type` is the new one. This change is taking place to make the field name easier to understand - we used to decide whether or not we cared about the Keycloak organization membership based on this field; now, we want all the organizations in Keycloak.

For the remainder of this document, we'll use `membership_type`.
:::

The `membership_type` field can be set to `managed`, `code`, or `auto`, and this determines how learners are allowed into the system:
- `auto` contracts are added to all members of the parent organization (as long as the contract is valid).
- `code` contracts require the use of an enrollment code to gain access to the contract.
- `managed` contracts are a weird third step that we support but don't really use.

Most contracts are either `auto` or `code`.

:::{note}
`auto` used to be called `sso`, and `code` used to be called `non-sso`. These values can still be used at present.
:::

Membership can be limited to a set number of seats by setting `max_learners`. This is important to set for contracts that require codes; if no seat limit is set, the system will create enrollment codes that allow for unlimited use.

In rare cases, we may charge a fee to gain access to courses within the contract. This can be set with the `price` field. In this case, learners are required to pay to enroll in a given course.

### Validity

Contracts can have a start and an end date set. If these are set, learners won't be able to gain access to the contract before or after these dates. They also won't be able to enroll in courses before or after these dates, either.

Contracts also have an "active" flag; if this flag is cleared, the contract is disabled. The start and end date settings still apply. (Technically, the organization itself also has an "active" flag, and contracts within inactive organizations are also inactive.)

### Enrollment codes

Enrollment codes are, at their core, discount codes. If a contract requires code-based access, the system creates codes for the contract as it needs.

Enrollment codes have special processing when they're used in the cart:
- They are attached to the contract course run's product, so they can't be used except with the course run they're intended for.
- Conversely, course runs that are for a B2B contract can't be purchased without applying the corresponding enrollment code.

Enrollment codes are created according to the settings in the contract:
- If a seat limit is set (`max_learners`), each course run in the contract gets a set of enrollment codes equal to the number of seats in the contract. E.g. if the contract specifies 100 learners maximum, and there are 3 course runs, then 300 codes will be created. These codes will be _one-time_ use codes that have a _fixed price_.
- If a seat limit is _not_ set, each course run in the contract gets _one_ enrollment code. That code is set to _unlimited_ use and has a _fixed price_.
- In either case, the fixed price is $0 unless the contract has a price set. The payment type is set to `sales` for these codes.

:::{important}
It's important that contracts that are going to use enrollment codes - as in, ones that are in organizations that _don't_ have an integrated identity provider - have a seat limit, or there is effectively no limit on the number of learners that can be in the contract. We can't verify membership for organizations with no identity provider, other than by validating the enrollment code, so any code that gets leaked out can be used by anyone.

If we do need to have a contract with no identity provider and "unlimited" seats, we should instead set the seat count to a high number and then increase it as we get closer to the seat limit.
:::

#### Redemptions

Enrollment codes can be redeemed by learners in one of two ways:

_Through Learn:_ In MIT Learn, we have an "attach" page. This is at `/enrollmentcode/<code>`. Learners navigating to this URL are added to the contract, and they're able to see the courseware resources available to them in their dashboard. The learner isn't enrolled in anything, though - they're just added to the contract.

_Through MITx Online_: Since these are discount codes, learners can submit enrollment codes into the discount code part of the cart page when they go to check out. We provide a link that adds the course run to the cart - learners using this link then enter the code, and they're able to check out. Finishing the process enrolls them in the course.

Note that a learner using a standard, one-time use code via either of these methods consumes it, but slightly differently between the two paths. If it's used on the "attach" page, the code is invalidated for further use on the "attach" page. If the learner uses the code as part of the checkout process, it invalidates the code for checkout and for the "attach" page. (In other words, the "attach" page checks that the code has been used either to attach the learner to the contract, or if it's been used in checkout.)

Enrollment codes are redeemed **automatically** sometimes. If the learner is in the contract, they don't have to continue to apply enrollment codes to enroll in courses. (We've already verified a code, so we're aware they're allowed to take courses.) Instead, learners clicking on the "Start Course" button in their dashboard in Learn trigger a process that creates an order and fulfills it for the course in MITx Online. This results in the learner being enrolled in the course, and the system consumes an enrollment code for this purpose.

If a contract that requires enrollment codes is changed, enrollment codes may be refreshed accordingly:
- If new courses are added, new codes will be created for those courses.
- If the seat limit changes, codes will be adjusted accordingly. (If the limit increases, new codes may be added; if the limit decreases other than to zero, codes may be removed.)
- Codes that have been used won't be modified.
