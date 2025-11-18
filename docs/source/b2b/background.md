# B2B System: Background and Theory of Operation

The goal of the B2B system is to allow for a third party to purchase access to content that we provide for other users. These users can identify themselves as being eligible for the content by either using a special code, or by logging in using a particular set of credentials. Once they have access to the purchased content, the learner is able to enroll and take the courses in a largely self-directed fashion.

The B2B system works through the ecommerce system. The codes we used - enrollment codes - are actually _discount codes_, and we generate orders when we grant access to purchased content.

## Data Model

When we enter into agreements to deliver content to an organization's users, we typically sign a contract (of some sort) that defines what we're delivering. The B2B system uses a similar structure at its core.

The B2B system revolves around the concept of an _organization_. The organization is an entity that we're engaged in business with. We store some basic information about the organization in the B2B system, such as the name, description, and logo. We also store the organization's Keycloak ID, if there is one. Learners within the system are linked to their organizations, and the system maintains these links in a handful of different ways. Being a member of an organization alone does not necessarily grant you any access to course resources.

_Contracts_ define a group of resources that are available to eligible learners within an organization. These resources can be programs or course runs. Contracts can various possible restrictions:
- They can be time-limited - contracts have start and end dates, and access to resources are gated according to these dates if set.
- They can have seat limitations - a contract can be set to only allow a set number of learners to access resources.
- They can require payment - a contract may specify a cost to be charged to the learner to access courses. (This is rare, but we do support it.)

The resources that a contract can grant access to can be course runs or programs:
- Course runs are linked directly to a contract. These are called _contract course runs_ and enrollment in them is restricted to learners that are attached to the associated contract.
- Programs are also linked to a contract. In this case, this is a many-to-many relationship; programs contain courses, so a program can contain courses that themselves have multiple runs that are linked to different contracts. So, programs need a more flexible mapping between themselves and the contract.

Access to the contract itself is also configurable. We have three options for access:

- _Auto_ contracts (which we also call _SSO_ contracts) grant access to the contract using the authentication system to determine what organization they belong to.
- _Code_ contracts (which we also call _non-SSO_ contracts) use enrollment codes to grant access to the contract.
- _Managed_ contracts combine the two - the learner must use an enrollment code, but they must also log in using their organization's credentials.

(These options are described in more detail later.)

## Authentication Model

The B2B system relies heavily on the SSO system that is in place for the Open Learning applications, which is built around Keycloak. Learners log in via Keycloak to the app, and Keycloak may allow them to log in using a federated identity provider, depending on their account.

Keycloak uses organizations itself to determine what identity provider the user should be directed to for login. A Keycloak organization contains a list of email domains that belong to the organization, and (optionally) configuration parameters for the organization's identity provider (IDP). If the organization has a configured IDP, then Keycloak will redirect the user through the IDP to log in.

When the user logs in, they begin the process by entering their email address, regardless of whether they have an account in the system. The user is then either sent to a login screen, prompted to sign up for an account, or is sent to their organization's IDP to log in. Since this is based on the user's email address, Keycloak can send the user to the IDP if their email matches up with an organization within the system, even if the user hasn't ever logged into the system before. For example, if you were to enter `someone@mit.edu` on the first screen, you would be sent through Touchstone for authentication, whether or not that's an actual account in Keycloak. If you're able to log in, Keycloak creates a user account for you locally and adds you to the MIT organization.

We can also add users to organizations manually. Not all organizations will have an IDP to authenticate against; nor will all of them have a defined list of email domains we can use to identify its users. (For example, if we wanted `janedoe@gmail.com` to be part of the MIT organization, we would have to manage that manually - we obviously can't add `gmail.com` as an email domain for MIT.) So, Keycloak allows users to be attached to the organization through its admin API and through its admin console.

The B2B system links its organizations to Keycloak organizations on the ID that Keycloak gives to each organization. Each organization gets a UUID from Keycloak, which is stored within the B2B system's organization record. A list of the user's Keycloak organizations are passed back to the app after they've logged in. The B2B system uses this list to reconcile the user's organization memberships.

For organizations that require manual member management, the B2B system can push additions to the organization to Keycloak via the admin API. Users that use an enrollment code to gain access to a given contract are added to the appropriate Keycloak organization automatically via the API.

When a B2B organization does not have an associated Keycloak ID, the reconciliation code just ignores it.

## Course Content

As noted, a B2B contract grants access to specific course content (either course runs, or programs) to eligible learners. These courses are restricted access - at best, we may offer a "verified" enrollment in a course that is publicly accessible, but usually there are specific course offerings that are geared towards the offering we're trying to sell. So, when we add a course to a B2B contract, we create a set of contract-specific course runs for the course (contract course runs). If we add a program, we iterate though the program and make contract runs for each of its courses.

edX itself does not split courses into a "course" and a "course run" like MITx Online does. Instead, it just has course runs, which can be re-run at will.

This creates a bit of an impass - we have a specific _course_ that is generally what we want to use for offerings that we may provide to various organizations, but we need to create _course runs_ for each contract, and, in edX, we only have course runs anyway. So, we can designate a given course run as a _source run_. When we add a course to a contract, the system looks for the course's source run and requests a re-run of that in edX for the contract.

## Basic Setup and Usage Workflow

Setting up a B2B organization and contract requires a few things to be done:

1. _Course creation_: The edX instance needs to have the courses that will be provided in the contract. These don't need to exist at the time the contract is created initially.
