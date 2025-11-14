# B2B System: Background and Theory of Operation

The goal of the B2B system is to allow for a third party to purchase access to content that we provide for other users. These users can identify themselves as being eligible for the content by either using a special code, or by logging in using a particular set of credentials. Once they have access to the purchased content, the learner is able to enroll and take the courses in a largely self-directed fashion.

The B2B system works through the ecommerce system. The codes we used - enrollment codes - are actually _discount codes_, and we generate orders when we grant access to purchased content.

## Data Model

When we enter into agreements to deliver content to an organization's users, we typically sign a contract (of some sort) that defines what we're delivering. The B2B system uses a similar structure at its core.

The B2B system revolves around the concept of an _organization_. The organization is an entity that we're engaged in business with. We enter into _contracts_ with the organization, and the contracts define what content is available to eligible learners. Teams in OL (or MIT as a whole) should be able to make a one-to-one mapping between a contract in the B2B system, and an actual contract that has been executed. We capture some data that describes how we deliver content in the app's contract record. This includes the maximum number of learners (seats), start and end dates for the contract, membership management process, and (rarely) an end-user cost for access.

An organization can contain any number of contracts.

The main goal of a contract is to define what courseware resources are available to eligible learners. We've made some minor changes to the courses models to facilitate this:
- Course runs are linked directly to a contract. These are called _contract course runs_ and enrollment in them is restricted to learners that are attached to the associated contract.
- Programs are also linked to a contract. In this case, this is a many-to-many relationship; programs contain courses, so a program can contain courses that themselves have multiple runs that are linked to different contracts. So, programs need a more flexible mapping between themselves and the contract.

Contracts also define how learners can utilize the resources in the contract. Learners need to be linked to the contract to be able to gain access to the resources it provides. We can do this in a number of ways:
- _Auto_ contracts (which we also call _SSO_ contracts) grant access to the contract using the authentication system to determine what organization they belong to.
- _Code_ contracts (which we also call _non-SSO_ contracts) use enrollment codes to grant access to the contract.
- _Managed_ contracts combine the two - the learner must use an enrollment code, but they must also log in using their organization's credentials.
