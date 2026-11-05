# Commands and Usage

B2B system data can be (and sometimes is required to be) managed through a set of management commands and Web interfaces.

## Management Commands

There are three management commands:
- [](#b2b_contract) - manages contracts and organizations
- [](#b2b_courseware) - manages courseware within a contract
- [](#b2b_list) - lists out data

This document will go over the basic use of the management commands. To get the full documentation for the command, run the command or subcommand with the `--help` option.

### b2b_contract

:Name: b2b_contract
:Description: Manages organizations and contracts within the B2B system.
:Subcommands:
    `create` - creates a new contract, with a default variant set

    `modify` - changes the parameters for an existing contract
:Description:
    The `b2b_contract` command can be used to set up a new contract for an existing organization. Organizations are created through the provisioning API (`POST /api/v0/b2b/provisioning/organizations/`), which creates the Keycloak organization alongside it.

    It can also be used to modify an existing contract. Modifying a contract does not touch its enrollment codes. After changing the price, seat count or membership type, run `b2b_codes validate` to bring the codes in line.

### b2b_courseware

:Name: b2b_courseware
:Description: Manages courseware objects attached to a contract.
:Subcommands:
    `add` - add courseware to a contract

    `remove` - remove courseware from a contract
:Description:
    The `b2b_courseware` command adds or removes courseware objects from a contract.

    :::{note}
    Courseware is most anything within the course system - a program, an individual course, or an individual course run. The command identifies which it is by the readable ID (course key) that you specify.
    :::

    In `add` mode, the command adds courseware to the contract.
    - If the object specified is a course run, it will be added to the contract, unless it is already in another contract, in which case it is left alone.
    - If the object specified is a course, a contract course run will be created.
    - If the object specified is a program, the program will be added to the contract, and it will create contract runs for each course in the program.

    In `remove` mode, the command removes courseware from the contract.
    - If the object specified is a course run, the mapping to the contract will be removed. (The run itself is not removed.)
    - If the object specified is a program, the mapping between the program and the contract will be removed. The contract runs won't be removed either.

    To understand the contract course run process, see [the Courseware Resources page](courseware).

### b2b_list

:Name: b2b_list
:Description: Lists detail about B2B objects.
:Subcommands:
    `organizations` - list organizations within the system

    `contracts` - list contracts within the system, or get enrollment codes

    `courseware` - list courseware objects attached to a contract

    `learners` - list learners within the B2B system

:Description:
    `b2b_list` lists out detail about various parts of the system.

    In `organization` mode, it just lists out the organizations.

    In `contracts` mode, it lists data about the contracts. You can filter by a particular organization. This subcommand also allows you to list the enrollment codes that have been created for the contract to a file.

    In `courseware` mode, it lists the courses/etc. that are attached to a contract or to an entire organization.

    In `learners` mode, it lists the learners attached to a contract or organization.

    With the exception of the `contracts --codes` mode, the system lists the data in tabular format using Rich, so the tables look nice.

## Wagtail/Django Admin Interface

B2B data is designed to be managed via Wagtail, and some things can be viewed or changed within the Django Admin as well.

### Hierarchy

Organizations and Contracts are Wagtail pages. An index page for organizations is be under the Home Page, and new organizations can be added here.

Each Organization page has its Contracts as child pages.

### In Wagtail

Organizations and contracts are created and edited in the staff dashboard, and only a few of their fields are still edited in Wagtail. There are some things to be aware of before using this interface, though.

- Organizations are best made in Keycloak, and then imported into MITx Online. There is a Celery task that will import organizations on a regular basis, or you can run the import manually. This will allow user management to be centralized within Keycloak. If you _must_ create an organization that exists outside of Keycloak, it's important that the Organization ID field remain blank.
- Do not modify the Organization ID within an Organization record. Doing so will break the sync between the org and the Keycloak org, and you'll end up with a duplicate organization when the Keycloak one is synced back into the system.
- Contracts are created and edited in the staff dashboard, on the organization's page under B2B Organizations, which also adds courseware and lists, assigns and expires enrollment codes. In Wagtail a contract's page edits the extra welcome message, the Google Sheet target and tab, and the order of its programs (adding or removing one there is not saved on a published page; on an unpublished page it is saved, so don't); its other fields are read-only there, and a contract can't be created or copied there. See [the provisioning API](provisioning_api.md).

### In Django Admin

The Contract and Organization pages can be viewed from within the Django Admin, but no changes can be made to them within this interface. This is to both funnel you into the Wagtail interface, and to prevent data issues, as Wagtail models are more complex than regular Django models. You can, however, drill down into the individual Contract and see what course runs and programs are associated with the Contract.

Course runs within Django Admin expose the contract they belong to. If you need to manually add or remove a course run to or from a contract, you can do this here.

Programs with in Django Admin expose the list of contracts they are associated with. You can update these as necessary from within this interface. Note that adding contracts to a program will not kick off the course run creation process for the program's courses. You will still need to do that with the management command, by adding the program to the contract again.

Users within Django Admin also list out which organizations and contracts the user belongs to. You can manage these as necessary. If you're adding an organization to a user manually, it is important that you check the "Keep Until Seen" box, or the system will potentially remove the user's organization membership the next time they load anything from MITx Online. Also, be aware that adding a contract to a user here does not automatically put them in the organization; you will need to add them to the org and the contract. (Similarly, removing the user from all of an organization's contracts won't also remove them from the org, and may result in the user being automatically added back to some contracts as per the rules set in the contract.)
