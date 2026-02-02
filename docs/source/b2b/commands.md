# Commands and Usage

B2B system data can be (and sometimes is required to be) managed through a set of management commands and Web interfaces.

## Management Commands

There are four management commands:
- [](#b2b_codes) - utilities for enrollment codes
- [](#b2b_contract) - manages contracts and organizations
- [](#b2b_courseware) - manages courseware within a contract
- [](#b2b_list) - lists out data

This document will go over the basic use of the management commands. To get the full documentation for the command, run the command or subcommand with the `--help` option.

### b2b_codes

:Name: b2b_codes
:Description: Utilities for managing enrollment codes within the system.
:Subcommands:
    `output` - outputs enrollment codes

    `validate` - checks/fixes enrollment codes

    `expire` - expire (remove) existing enrollment codes
:Description:
    The `b2b_codes` command allows you to output the list of codes, validate them, and expire unnecessary codes. The `output` subcommand takes over the functionality of the `b2b_list contract --codes` command.

    `b2b_codes output`, by default, outputs a _functional_ set of B2B enrollment codes for a given contract or organization (or the entire system, but this is not recommended). It can also output _all_ the available codes, output usage information for the codes, or output usage statistics for codes. Code output can be in table, CSV, or JSON formats and can be redirected to a file for the latter two.

    `b2b_codes validate` checks the codes within the contract or organization and ensures they're set up correctly. Attached course runs are checked to ensure they have a product. Products will be created for runs that don't have one, and existing products will be checked to ensure they have the correct pricing. Codes that aren't needed are removed, and the remainder are checked to ensure they have the correct redemption type and amounts set. Missing codes are created. (Codes that have been redeemed are not removed.)

    `b2b_codes expire` removes unused codes from the contract or organization, and outputs a list of the codes that were removed. The main use case for this is if a contract's codes becomes public; the codes can be removed and `b2b_codes validate` can then be used to generate new ones.

### b2b_contract

:Name: b2b_contract
:Description: Manages organizations and contracts within the B2B system.
:Subcommands:
    `create` - creates a new contract (and optionally organization)

    `modify` - changes the parameters for an existing contract
:Description:
    The `b2b_contract` command can be used to set up a new contract. It can also create an organization for you, if necessary.

    It can also be used to modify an existing contract. Changing certain parameters - pricing, seat count, and activation dates especially - will also caused _unredeemed_ enrollment codes to be updated, and new ones to be created, where appropriate.

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
    - If the object specified is a course run, it will be added to the contract (unless it's already associated with a contract, and `--force` isn't set)
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

Under each Organization page, any number of Contracts can be created as child pages.

### In Wagtail

You can create new and manage existing organizations and contracts within Wagtail. There are some things to be aware of before using this interface, though.

- Organizations are best made in Keycloak, and then imported into MITx Online. There is a Celery task that will import organizations on a regular basis, or you can run the import manually. This will allow user management to be centralized within Keycloak. If you _must_ create an organization that exists outside of Keycloak, it's important that the Organization ID field remain blank.
- Do not modify the Organization ID within an Organization record. Doing so will break the sync between the org and the Keycloak org, and you'll end up with a duplicate organization when the Keycloak one is synced back into the system.
- Contracts can be created but at this point you cannot add courseware objects to them without using the management commands. Similarly, you cannot get out the enrollment codes other than the management command (or looking in Django Admin). (We will build these interfaces out but they're not ready as of this writing.)

### In Django Admin

The Contract and Organization pages can be viewed from within the Django Admin, but no changes can be made to them within this interface. This is to both funnel you into the Wagtail interface, and to prevent data issues, as Wagtail models are more complex than regular Django models. You can, however, drill down into the individual Contract and see what course runs and programs are associated with the Contract.

Course runs within Django Admin expose the contract they belong to. If you need to manually add or remove a course run to or from a contract, you can do this here.

Programs with in Django Admin expose the list of contracts they are associated with. You can update these as necessary from within this interface. Note that adding contracts to a program will not kick off the course run creation process for the program's courses. You will still need to do that with the management command, by adding the program to the contract again.

Users within Django Admin also list out which organizations and contracts the user belongs to. You can manage these as necessary. If you're adding an organization to a user manually, it is important that you check the "Keep Until Seen" box, or the system will potentially remove the user's organization membership the next time they load anything from MITx Online. Also, be aware that adding a contract to a user here does not automatically put them in the organization; you will need to add them to the org and the contract. (Similarly, removing the user from all of an organization's contracts won't also remove them from the org, and may result in the user being automatically added back to some contracts as per the rules set in the contract.)
