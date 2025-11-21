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

    To understand the contract course run process, see this other page.

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
