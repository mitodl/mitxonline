
B2B Contract Management
=======================

B2B contracts can be managed via the command line and Django Admin.

..

   Contracts will also be manageable via Wagtail.


The management commands you will need to use are:


* ``b2b_contracts`` - manages organizations and contracts
* ``b2b_list`` - lists data about B2B resources

Quick Setup
-----------

UAI Scenario: SSO, No Price, Uncapped
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is how UAI contracts that have SSO integration with the host organization are set up.

**Prerequisites:** You need at least one course to add to your contract. It does not need course runs.


#. Create a contract with a new organization:
   ``b2b_contract create UniversityX "UniversityX Contract" sso --description "Test uncapped SSO contract"``
#. List the details about your new organization:
   ``b2b_list organizations``
#. List the details about your new contract: *(You'll need the ID from the output for the next step.)*
   ``b2b_list contracts``
#. Add the course to the contract. This will also create a course run for the course:
   ``b2b_contract courseware <contract ID> <course readable ID>``
#. List the details about the contract's courseware:
   ``b2b_list courseware --contract <contract ID>``

Quick Setup: Non-SSO, No Price, Capped Learner Count
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is how a B2B contract would be set up typically.

**Prerequisites:** You need at least one course to add to your contract. It does not need course runs.


#. Create a contract with a new organization:
   ``b2b_contract create UniversityX "UniversityX Contract" non-sso --max-learners 200 --description "Test capped non-SSO contract"``
#. List the details about your new organization:
   ``b2b_list organizations``
#. List the details about your new contract: *(You'll need the ID from the output for the next step.)*
   ``b2b_list contracts``
#. Add the course to the contract. This will also create a course run for the course:
   ``b2b_contract courseware <contract ID> <course readable ID>``
#. List the details about the contract's courseware:
   ``b2b_list courseware --contract <contract ID>``
#. Get the enrollment codes for the contract:
   ``b2b_list contracts --codes <contract ID>``
   The codes will be in a CSV file named ``codes-<contract ID>.csv``

Quick Setup: User Provisioning
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The easiest way to get users *into* a contract is to just add them to it: from within the Django Admin, navigate to Users, find the user you want to add in, and then add a new relationship using the table at the bottom of the page.

The second easiest way is to set up a contract that involves enrollment codes, and then use the enrollment codes. The output from ``b2b_list contracts --codes`` includes a URL that will add the resulting product to the cart. You then need to use the code and check out.

Contracts and Organizations
---------------------------

Contracts are the core data element. They belong to an organization, which provides not much more than some metadata and grouping for the contracts and the learners attached to them.

You can create and manage contracts using the ``b2b_contract create`` and ``b2b_contract modify`` commands.

``b2b_contract create``
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Creates a contract and optionally its organization.

Syntax: ``b2b_contract create <org name> <contract name> sso|non-sso``

Options:


* ``--start`` / ``--end``\ : Set a start and end date for the contract. These dates will be used when creating the contract's course runs.
* ``--max-learners``\ : Cap the number of learners that can be attached to the contract.
* ``--price``\ : Contracts can either allow free enrollment for associated learners, or specify a fixed price for enrollment. If it's the latter, use the ``--price`` option; you will have fixed-price discounts for the learners to use to gain access to the courses.
* ``--description``\ : A description for the contract. This is a text field and can be as long as necessary.

Notes:


* Names should be descriptive. A slug will be automatically generated for the contract and the organization.
* Specify the organization's name, not an ID. Supply ``--create`` if the organization doesn't already exist - it will be created. Otherwise, the command will look it up based on the name.

Choosing an integration type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The integration type can be either ``sso`` or ``non-sso``. This has some bearing on how related data elements are set up in the system.

Non-SSO contracts:


* Users gain access to the contract (and thus the resources within it) via enrollment codes.
* Enrollment codes are *always* generated when the contract is modified in any way (other than to deactivate it).
* There *should* be a learner cap on these contracts. (This is usually the case.)

SSO contracts:


* Users can gain access either through enrollment codes *or* by automatic attachment on login, depending on whether or not the contract has specifies a price for the learner or not.
* Enrollment codes are only generated if the contract specifies a *price* - in that case, the learners need to pay to gain access.
* Learners can still be capped; we just enforce that cap elsewhere.

SSO contracts require additional setup to be fully functional. The SSO system itself needs to be federated with the host organization's identity provider. This isn't done by the MITx Online code - it requires some work within Keycloak.

``b2b_contract modify``
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Updates a contract's parameters.

Syntax: ``b2b_contrac modify <contract_id>``

Options:


* ``--start`` / ``--end``\ : Set a start and end date for the contract. These dates will be used when creating the contract's course runs.
* ``--max-learners``\ : Cap the number of learners that can be attached to the contract.
* ``--price``\ : Contracts can either allow free enrollment for associated learners, or specify a fixed price for enrollment. If it's the latter, use the ``--price`` option; you will have fixed-price discounts for the learners to use to gain access to the courses.
* ``--active / [--inactive|--delete]`` - Activate or deactivate the contract.
* ``--no-price / --no-learner-cap / --no-start-date / --no-end-date`` - Remove price, learner cap, start/end dates.

Notes:


* If you remove the price or learner caps from the contract, any unused enrollment codes should be adjusted. Note that removing the price essentially means "set it to $0" - the enrollment codes will be set to fixed price $0 discounts.
* If you remove the start and end date, any existing course runs will not be modified.

Courseware
----------

Once a contract is created, it needs resources to provide to the learners. Use ``b2b_contract courseware`` for this.

``b2b_contract courseware``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Add or remove courseware from the contract. (This means either programs or courses, but it could mean more types in the future.)

Syntax: ``b2b_contract courseware <contract_id> <courseware_readable_id>``

Options:


* ``--no-create-runs`` - don't create runs. You probably don't want this, but it can be useful if you want to create just a course shell for content folks to use, for example.
* ``--remove`` - Remove the course from the contract. This *will* unset the existing course runs - they won't be deleted, but they also won't be associated with the contract anymore.

Notes:


* The courseware ID is the readable ID. Except when using `--remove`, don't specify runs.
* If you specify a program, it will create runs for all the courses within the program. You may need to re-run this if the program is modified.

Choosing a Courseware ID/edX Run Creation:

The ``courseware`` command will try to do one of a few things depending on what's passed as a courseware ID.


* If a course ID is passed, it will try to create a single course run for the contract, and will attempt to create a re-run in edX for the source course run.
* If a course run ID is passed, it will assign the run to the contract, unless the run is already assigned to a contract. If the run is assigned to a contract, you'll get an error.
* If a program ID is passed, it will loop through the requirements tree and try to make new runs for each of the listed courses. It will skip any runs that the contract already has.

If you want the system to automatically create re-runs in edX, you will need to make sure you have some additional configuration settings in place.


* In edX, you will need a service account that has at least staff rights to be able to create course runs. Create an account via Django Admin (or other method), and make sure the staff and superuser flags are set to True. Also, make sure it has a profile - it just needs one at all; filling out just the name is sufficient.
* Then, make an OAuth2 application for the service account. The Client Type should be "Confidential" and the Authorization Grant Type should be "Client credentials". Make sure the User is set to your service account user.
* Set the ``OPENEDX_COURSES_SERVICE_WORKER_CLIENT_ID`` and ``OPENEDX_COURSES_SERVICE_WORKER_CLIENT_SECRET`` settings in your ``.env`` to the ID and secret from the new application.


Courseware Setup in edX
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

B2B courses in edX should be set up in a particular fashion, both to make sure we can identify them within edX easily, and to allow the system to automatically create runs for new contracts.

Each B2B course starts with a source course. Usually, these are separate courses and runs, but not always. If you're creating a new course, it should be created in edX with the organization ``UAI_SOURCE`` and the run tag ``SOURCE``. A corresponding course run in MITx Online should also be created. The ``import_courserun`` command can be used to help facilitate this. If you want to use an existing course, you should create a ``SOURCE`` run for it from the run you want to use as the source course in edX.

When associating a course or program with a contract, the ``b2b_contract courseware`` command will try to create a contract-specific run for each source course (either the one you've specified or the ones that are in the specified program). It does this by trying to find an appropriate source course run for the course in MITx Online. It will look first for a course run with the run tag ``SOURCE`` - if it can't find this, it will use whatever the first course run is in database order. **This is probably not what you want** - you should try to have a ``SOURCE`` course run if at all possible.

Course runs will be created using the start/end date of the contract, if those dates are set. If the contract is open-ended, the runs will be created with the current time/date as the course and enrollment start date and no end date. The runs will be created with the organization set to ``UAI_`` and the organization key set in the org record, and the run key will be set to the current year, ``C``, and the ID of the new contract.


Listing Data
------------

The ``b2b_list`` command contains a handful of subcommands for listing out the data within the B2B system. Some of this you can get through the Django Admin and/or Wagtail admin but this is more of a one-stop-shop for this data.

``b2b_list organizations``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Lists out the orgs in the system.

Syntax: ``b2b_list organizations``

Options:


* ``--org / --organization`` - only show the specified contract ID

Notes:

This is pretty basic. It's just for verifying the base data about the org.

``b2b_list contracts``
^^^^^^^^^^^^^^^^^^^^^^^^^^

Lists out the contracts within the system.

Syntax: ``b2b_list contracts``

Options:


* ``--org / --organization`` - Limit the output to contracts for the specified organization ID.

Notes:

This is also pretty basic, but you'll need the contract ID to add courseware.

``b2b_list courses --codes``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Lists the enrollment codes in the contract.

Syntax: ``b2b_list courses --codes <id>`` where ID is the contract ID

Options:


* ``--codes-out <filename>`` - Write the codes to a file using this name. Otherwise, the output file is ``codes-<id>.csv``.

Notes:


* This is sort of a separate command from the base ``contracts`` command, but also not really.
* The resulting CSV file contains 4 fields:

  * Code: the code itself. This is a UUID.
  * Product: the product that the code can be used for.
  * Redeemed: whether or not the code has been redeemed.
  * Product URL: the URL to distribute to the learner; this will start a new basket for them with just the product in it, so they can apply and use the code.

Enrollment Codes and Products
-----------------------------

When courseware items are attached to contracts, a few things happen:


* Runs are created. At this point, this is exclusively course runs.

  * If a standalone course is added, then it's one run for the course.
  * If a program is added, then a course run is created for each course that's listed in the program's requirements.
  * In all cases, the run's dates are set to either mirror the contract, or set with start dates in the past so learners can get into the course. The courses are marked live and self-paced. If you need to modify this afterwards, you can do so through the normal methods.
  * Notably, CMS pages *are not* created for these. They will not be accessible through the front end. But they should show up on dashboards for learners who are enrolled in the course.

* Products are created for each run.

  * If the contract specifies no price, these are set to $0.
  * If the contract does specify a price, these are set to the price in the contract.

* Discount codes are created, if necessary.

  * These are enrollment codes - enrollment codes are discount codes.
  * Codes are created and linked to the individual products that were created for the contract.
  * If there's *no learner cap*\ , there is *one* code per product, set to unlimited use.
  * If there's a learner cap, there is one code *per learner* per product, set to one-time use. (That means if the cap is set to 200 learners, and the contract specified 20 courses, there will be 4,000 created codes.)
  * In either case, the codes are set to Fixed Price with the price specified in the contract ($0 or more), payment type Sales, and the is bulk flag is set to True.

When the contract is updated, or courseware is attached to the contract, the system will update or create codes in the system:


* If the modifications mean that the cap is removed, the integration type is SSO, and the price is set to zero, then all unredeemed codes are deleted. This is the only scenario in which the system will remove codes.
* Otherwise:

  * If the learner cap is removed, the redemption type changes from One Time to Unlimited.
  * If the price is adjusted, the price in the discount code is also adjusted.
  * If new courses are added, and as such new products are created, new discount codes are also created.
  * If the learner cap is *changed* (increased or decreased), codes are created or deactivated accordingly.

This adjustment happens any time the contract is saved or courseware is added. This is potentially an expensive operation, so it's queued.

User Provisioning / New Rules for Checkout
------------------------------------------

In a lot of cases, learners will be provisioned based on what's in their Keycloak profile, because they'll log in using federated SSO with their host organization. The system will note this and then attach the user to the appropriate contract when they get back into MITx Online.

In a lot of *other* cases, learners will have to use an enrollment code. This works using the ecommerce system. Learners use the special URL that adds the course to their basket, apply the provided code, and then check out. This enrolls them in the course (and collects any fee that may be required).

Most of the time, a B2B contract will be set up to allow the learner to access resources for free. The ecommerce system additionally usually just processes zero-value baskets without further input from the learner. This is a problem for B2B contracts, since we need them to use the enrollment code. So, some changes have been made to the checkout process. If the basket is zero value *but* the product is linked to a B2B run, then we *do* present them with the basket screen. They won't get a checkout button until they've applied the code (which was a happy accident). Once they've applied it and hit the checkout button, the system will then notice it's a zero-value cart, and complete the process; they won't have to do a round-trip through CyberSource.

If the contract specifies a price, then the learner will arrive at the Cart page as normal. The process is otherwise identical to the process they'd take if they were buying a regular upgrade.

We additionally have added more checks to discount codes and products in the cart. Specifically, if the learner has a product linked to a B2B course, they are *not allowed* to check out without applying the correct discount code. The system will kick them back to the cart page with the invalid discount message.

Manual Management
^^^^^^^^^^^^^^^^^

In the Django Admin, we've added a new inline to User to display the contracts the learner belongs to. You can add or remove associations here. At present, we don't expose this in management commands.

If you need to provision a user *quickly*\ , this is the easiest way to do it, as long as the user already exists.

Other Management
----------------

The plan is to allow for orgs and contracts to be managed through the Wagtail interface. To that end, organizations and contracts are really Wagtail pages.

If you run ``configure_wagtail``\ , you will see a new top-level Organizations page under Home Page. You should be able to create and see organizations in there, and you should be able to create contracts for those organizations from there too. *If you need to manually edit a contract or org* you should do it using the Wagtail interface, if you can't do it for whatever reason from the command line.

The Wagtail interface currently does not allow you to manage courseware assignments or retrieve the list of enrollment codes, so this is not a complete interface.

We also expose the contracts and pages via the Django Admin. This is a read-only interface.
