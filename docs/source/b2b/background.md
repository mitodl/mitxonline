# Background and Theory of Operation

The Universal AI project required us to build out the ability to grant access to specified programs and courses within MITx Online to other organizations, with the goal of allowing those organizations to allow their members to complete the AI-focused courses that we offer. This required a few pieces: we needed to be able to define who those organizations were; we needed to be able to determine what courses should be offered to each organization; we needed some reasonably self-service ways for learners to take these courses; and we needed to be able to have a federated login system, so those learners could authenticate with their organization credentials.

The B2B system was built out to add most of these functional pieces to MITx Online. It adds:
- The ability to create organizations for UAI organizations, and then assign course content to them
- The ability for organization members to gain access to courses - either automatically or via a special coded URL
- Integration with the SSO system we have in place to ensure organization members are identified properly within MITx Online
- A set of APIs that Learn can use to present UAI-specific content to the learner

While designing the system, it became quickly apparant that this system would be pretty close to the B2B system within xPRO, so it was designed to be capable of handling those sorts of transactions as well. So, as we roll the xPRO functionality into Learn and MITx Online, we'll be able to handle business-to-business sales of course content seats as well. (This is why this is called the "B2B system" and not the "UAI system".)

## Theory of Operation

The B2B system starts with a set of courses that have been developed or modified with the intent of providing them to members of other organizations. We also need to enter into agreements with those organizations to provdie the content to them. (These operations can happen asynchronously and we may develop further content for the organization later.)

Once we're ready to on-board the organization, we enter some data into the system:
- We create a record for the organization. This is typically done in Keycloak and then synced to MITx Online, but we occasionally have organizations that are separate. If the organization is added via Keycloak, we additionally have the option to federate with their identity provider to provide login.
- We create a record for the contract. The contract connects learners and courseware objects to the organization and establishes the rules for access.
- We associate courses with the contract. This kicks off a re-run of the "base" course run for the course in edX that results in a course run specific for the contract.
- If necessary, the system creates enrollment codes for the contract. Learners can use these codes to gain access to the contract's courseware resources. We distribute these to the appropriate person at the organization for wider distribution.

Contracts specify how learners can access resources:
- Contracts can be set to "auto", which means that any member of the organization has access to the resources. The system automatically adds (or removes) the learner from these contracts when they log in.
- Contracts can be set to "code", which means that enrollment codes are required for access. Learners use enrollment codes in one of two ways, and this grants them access to the contract and puts them in the organization.
- If a contract specifies this, learners may be required to pay a fee to access the resources. This works like the "code" type, but learners are then redirected through the ecommerce system when they try to enroll in any of the contract's courses.

Finally, learners can then access resources:
- The system reconciles the learner's organizations and contracts with Keycloak on login. Learners are automatically granted access to some contracts, and access to contracts may be removed if the learner's organization memberships change.
- Learners can use the dashboard in MIT Learn to see what contract they can access. From there, they can enroll in courses, access courses they've enrolled in, and see any certificates that they've earned.
- Learners can use an enrollment code to gain access to new contracts. They can do this by using a special link that enrolls them in a particular course: they are sent through the ecommerce system, and the learner supplies the enrollment code to complete the transaction, upon which they're added to the contract (and organization, if necessary). Or, they can use a special URL in Learn that simply adds them to the contract.

The course enrollment process for B2B contract course runs is slightly different:
- If the contract is an "auto" contract, learners are simply enrolled in the course once their membership is validated.
- If the contract uses enrollment codes, learners only need to explicitly supply an enrollment code once, either by the Learn "attach"/"enrollmentcode" URL or by using the cart link. After that, they are in the contract and organization, and they can enroll in new courses using a one-click process from the Learn dashboard. When they click "enroll" on the dashboard, the system actually prepares an order for the learner, attaches an enrollment code for the course, and then completes the order; this process results in the learner being enrolled in the course.
    - There is an exception to this. If the contract uses enrollment codes _and_ requires payment, clicking "enroll" sends the learner to the Cart in (currently) MITx Online, which will allow them to pay the course fee.

## Functional Pieces

B2B focuses on a few things:
- Organizations and contracts, which define the organization we're affiliating with to provide content, and define what content we're providing
- Course content, which is often (but not always) specific to a given _sort_ of offering that we're providing (e.g. the Foundational AI modules, or a set track of professional development courses for CIOs), and has access restricted to the organizations we're providing the content
- The learners within the organizations, who need to be identified as organization members, and who need to gain access to the content according to the rules set in the system and in the contract

The basic flow for rolling out an affiliation with an organization is:

1. We develop a set of courses that we can provde to other organizations.
2. We enter into an agreement (contract) with the organization to provide them access to these courses. The agreement sets what courses are to be provided, deliniates who should be allowed to access the courses, and provides other metadata that we need.
3. We set up the organization within the B2B system. (In addition, we take some steps to set the organization up within the Keycloak SSO system as well.)
4. We set up the contract for the organization, which contains the metadata relevant to MITx Online, and we add the courses to the contract.
5. Learners gain access to the contract in one of two ways - either automatically on login, based on their credentials; or via codes the learners can redeem for access.
6. Learners are able to see the content they've been given access to on their dashboards in the Learn app, and are able to enroll in and take courses through MITx Online.

The B2B system contains a few key pieces that make this workflow function:

1. Organizations and contracts: we've added a system to manage these within MITx Online, and we've built it to work with Keycloak so we can control membership in both contracts and organizations.
2. Ecommerce: we leverage the existing ecommerce system to track and coordinate enrollment in a given contract's courses. A part of this is enrollment codes - we utilize the discount system to process enrollment codes, and optionally charge organization members for access if we need to (though this is a very rare occurance).
3. Courses: we use edX to deliver the course content, as we do for other non-B2B course offerings, and we've added additional support for some edX APIs to allow contracts to have unique runs of the courses we've added to them. In addition, we've made some small changes to the course models in MITx Online to facilitate this.
4. Keycloak: we use the organization support within Keycloak to provide optional federation with an organization's identity provider system; users within these organizations can then log in with their organization's credentials and be automatically added into the B2B organization on our side (along with certain kinds of contracts).
