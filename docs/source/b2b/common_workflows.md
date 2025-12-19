# Common Workflows

These are some common workflows for the B2B system that can be used verbatim or as a template or guide to operation.

## Prerequisites

If you're testing locally, you'll need a mostly complete Learn stack set up. This means MITx Online, Learn, and edX/Tutor; all configured to talk to each other. You'll need a shared APISIX and Keycloak instance set up as well and configured to handle ingress to MITx Online and Learn.

You'll need organizations enabled in Keycloak, and you'll need at least one set up. You don't need to have an identity provider configured for the organization, but you do need to have email domains set if Keycloak should automatically managed the organization members. The setup for a Keycloak organization is described [in the Keycloak Server Administration documentation](https://www.keycloak.org/docs/latest/server_admin/index.html#_managing_organizations) (and will vary depending on what version of Keycloak is in use).

You'll need MITx Online to be set up with a Keycloak admin, so that it can work with organization data within Keycloak. The best documentation for this is in [the PR that merged in the implementation.](https://github.com/mitodl/mitxonline/pull/2948)

You'll also need at least one course with a designated source course run.

### Course considerations

Source courses _should_ follow some conventions, so we can identify that the course is a source course:

- The organization should be set to something appropriate - for Universal AI, we use `UAI_SOURCE`. B2B source runs should be something like `B2B_SOURCE`.
- The run tag should be something appropriate as well - usually, we use `SOURCE` for this.
- In MITx Online, the resulting course run should have the "source run" flag set. This is the only hard requirement.

You can technically use _any_ course as a source course, but it should have a specific run designated as a source run.

Creating a course is a two part process. The course needs to be created in edX, and a representation for it needs to be created in MITx Online.

### Creating a course: edX setup

Creating a new course is easiest to do by starting within edX itself. This guide won't go through the full course setup process, but the process to create a minimally viable course is:

1. Log into edX Studio.
2. Click "New course" at the top.
3. Fill out the form. The "Organization" should be set accordingly (so, either `UAI_SOURCE` or `B2B_SOURCE`) and the "Course run" should be set to `SOURCE`.
4. Click Create.
5. If necessary, set the dates on the course. Find "Set dates" and click that, and you should be able to set the dates on the course and do some other things (set pacing, adjust license, etc.).
   - This is more necessary for local testing - the default start date for a course is 2030-01-01. You'll want to set this and the enrollment start date to a more reasonable value so you can enroll in the course.
   - If the course will be live and _isn't_ ready yet (which will be the case for a brand new course), you can leave the default dates as is - this will keep people from seeing it and enrolling.

__**Alternatively**__: You can also re-run an existing course in edX to create a source course. (This is often how these are created in the live environment.) To do this:

1. Log into edX Studio.
2. Find the course you want to re-run.
3. From the kebab menu, click "Re-run course".
4. Follow steps 3-5 above. You'll be able to change most settings about the new re-run, except the course number.

### Creating a course: MITx Online setup

MITx Online has a command that can import an edX course, and that is the easiest way to create the corresponding records in MITx Online.

The command is `import_courserun` and you will need to set some of the flags it provides:
- Specify `--courserun <courserun>` - this will be the readable ID (course key) for the edX course created above.
- Specify `--source-course` - this will set the source course run flag on the resulting course _run_.
- Specify `--ingest-content-files-for-ai` - this will allow the chatbots to digest the course contents, so they can be used in the course. (You _may not_ want to do this but typically we do want the chatbots in the B2B/UAI courses.)
- Specify both `--live` and `--create-cms-page`. This will set the course to "live" and create a CMS page, which will be published. Some of the APIs require that the CMS page for the course to exist and be published before the course shows up. _TODO: make sure this is correct_

So, a full command line would look like:

```bash
./manage.py import_courserun --courserun course-v1:UAI_SOURCE+12.345x+SOURCE --source-course --ingest-files-for-ai --live --create-cms-page
```

MITx Online will then query edX for the course details, and create:
- A course record
- A course run record, with the source course run flag set, and with the dates set according to the edX course run
- A CMS page for the course, with as much data as it can pull from the edX course

:::{tip}
The [`b2b_courseware`](/b2b/commands.md#b2b_courseware) command also can import edX course runs, and assign them to contracts. This takes this process one step further in that you get not only the source course run, but also the _contract_ course run, and you get that contract run in both MITx Online and edX. However, for this guide, it's assumed you're starting without any other B2B data in place.
:::

:::{note}
Keep in mind that "course" and "course run" mean different things between edX and MITx Online.
- In edX, there is only "course run".
- MITx Online splits those into "courses" which each have "course runs". An MITx Online course run maps to an edX course run.
:::

## UAI contract with federated IDP

This scenario describes:
- A new organization with one "managed"-type contract
- Organization membership entirely controlled by Keycloak
- Contract membership controlled by Keycloak

This is the most common setup for UAI contracts.

> For local testing, you can use email domain matching rather than setting up an IDP.

The settings for this scenario:

| Setting | Value |
|---|---|
| Organization | IDP University |
| Org Slug | IDPU |
| Contract | IDP University Contract |
| Course Title | Intro to Courses |
| Course Key | `course-v1:UAI_SOURCE+A.0001x` |

**Setup steps:**

1. Ensure the courses for the contract are set up with source course runs.
1. Import organizations from Keycloak: `./manage.py sync_keycloak_orgs`
2. Create the contract and org: `./manage.py b2b_contract create "IDP University" "IDP University Contract" managed`
3. Get the contract ID: `./manage.py b2b_list contracts --org IDPU`
   This should result in output like this:
   ```
                                                                Contracts
    ┏━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┳━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━┓
    ┃ ID ┃ Name               ┃ Slug               ┃ Org Name       ┃ Integration ┃ Start ┃ End ┃ Active ┃ Max Learners ┃ Price ┃
    ┡━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━╇━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━┩
    │ 59 │ IDP University     │ contract-58-idp-u… │ IDP University │ managed     │       │     │ Yes    │ Unlim        │       │
    │    │ Contract           │                    │                │             │       │     │        │              │       │
    └────┴────────────────────┴────────────────────┴────────────────┴─────────────┴───────┴─────┴────────┴──────────────┴───────┘
    ```
4. Add the courseware: `./manage.py b2b_courseware add 59 course-v1:UAI_SOURCE+A.0001x`

**Result:**

In MITx Online:

1. A new organization should be created and should show up in `b2b_list organizations`
2. The organization's SSO ID should be set to the UUID from Keycloak.
2. A new contract should be created and should show up in `b2b_list contracts`
3. The course should be added to the contract, which you should be able to see in `b2b_list courseware`.

In edX:

1. A new course run should exist, with key `course-v1:UAI_IDPU+A.0001x+2025_Cxx` (where 2025 is the current year, and Cxx is C and the contract ID).

After logging in as a user in the organization:

1. The user account should be attached to the organization and contract.
2. In Learn, the user should see the organization on their Dashboard.
3. The Dashboard for the organization should show the course that was added, with a "Start Module" button.
4. Clicking "Start Module" should enroll the user and bring them to the course.

## UAI contract with enrollment codes

This scenario describes:
- A new organization with one "code"-type contract
- Organization membership managed by Keycloak
- Contract membership controlled by enrollment codes
- A maximum membership of 15 people in the contract

This is the second most common setup for UAI contracts. UAI contracts often omit the seat limit, though.

> This scenario still assumes that Keycloak will be controlling organization membership automatically, either by using email domain matching or a configured IDP. For local testing, set up an email domain so it will automatically add users to the org.

The settings for this scenario:

| Setting | Value |
|---|---|
| Organization | University of Enrollment Codes |
| Org Slug | UCODE |
| Contract | University of Enrollment Codes Contract |
| Course Title | Intro to Courses |
| Course Key | `course-v1:UAI_SOURCE+A.0001x` |

**Setup steps:**

1. Ensure the courses for the contract are set up with source course runs.
1. Import organizations from Keycloak: `./manage.py sync_keycloak_orgs`
2. Create the contract: `./manage.py b2b_contract create "University of Enrollment Codes" "University of Enrollment Codes Contract" code --max-learners 15`
3. Get the contract ID: `./manage.py b2b_list contracts --org UCODE`
   This should result in output like this:
   ```
                                                                Contracts
    ┏━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┳━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━┓
    ┃ ID ┃ Name               ┃ Slug               ┃ Org Name       ┃ Integration ┃ Start ┃ End ┃ Active ┃ Max Learners ┃ Price ┃
    ┡━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━╇━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━┩
    │ 102 │ University of Enrollment Codes     │ contract-58-idp-u… │ University of Enrollment Codes │ managed     │       │     │ Yes    │ Unlim        │       │
    │    │ Contract           │                    │                │             │       │     │        │              │       │
    └────┴────────────────────┴────────────────────┴────────────────┴─────────────┴───────┴─────┴────────┴──────────────┴───────┘
    ```
4. Add the courseware: `./manage.py b2b_courseware add 102 course-v1:UAI_SOURCE+A.0001x`
5. Get the enrollment codes: `./manage.py b2b_list contracts --codes 102`
   The codes will be written to a file called `codes-102.csv`.

**Result:**

In MITx Online:

1. A new organization should be created and should show up in `b2b_list organizations`
2. A new contract should be created and should show up in `b2b_list contracts`
3. The course should be added to the contract, which you should be able to see in `b2b_list courseware`.
4. 15 enrollment codes should have been created.

In edX:

1. A new course run should exist, with key `course-v1:UAI_CODEU+A.0001x+2025_Cxx` (where 2025 is the current year, and Cxx is C and the contract ID).

After logging in as a user in the organization:

1. The user account should be attached to the organization, but not the contract.
2. In Learn, the user should see the organization on their Dashboard, but there should not be anything in it for this particular contract.
3. The user should be able to use the enrollment code to gain access to the contract.
   1. They can use the link that is provided in the enrollment code CSV file, which will enroll them in the course as well.
   2. They can use the enrollment code at `/enrollmentcode/<code>` on Learn, which will add them to the contract.
3. The Dashboard for the organization should show the course once they've used the enrollment code. They will be enrolled depending on what pathway was used to consume the code, so they will either see "Continue Module" or "Start Module".
4. If the user's not enrolled already, clicking "Start Module" should enroll the user and bring them to the course.

## Single-course B2B contract

This scenario describes:
- A new organization with one "code"-type contract
- Organization membership managed by MITx Online
- Contract membership controlled by enrollment codes
- A maximum membership of 15 people in the contract

This is a setup that would be more typical for a B2B contract, and assumes Keycloak is _not_ matching anything in particular for the organization membership. Using the enrollment code will instead add users to the contract. This still requires that an org be set up in Keycloak, though, and the org should have no email domains configured or identity providers set up.

The settings for this scenario:

| Setting | Value |
|---|---|
| Organization | BigCo Codes |
| Org Slug | BIGCO |
| Contract | BigCo Codes Contract |
| Course Title | Intro to Courses |
| Course Key | `course-v1:UAI_SOURCE+A.0001x` |

**Setup steps:**

1. Ensure the courses for the contract are set up with source course runs.
1. Import organizations from Keycloak: `./manage.py sync_keycloak_orgs`
2. Create the contract: `./manage.py b2b_contract create "BigCo Codes" "BigCo Codes Contract" code --max-learners 15`
3. Get the contract ID: `./manage.py b2b_list contracts --org BIGCO`
   This should result in output like this:
   ```
                                                                Contracts
    ┏━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┳━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━┓
    ┃ ID ┃ Name               ┃ Slug               ┃ Org Name       ┃ Integration ┃ Start ┃ End ┃ Active ┃ Max Learners ┃ Price ┃
    ┡━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━╇━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━┩
    │ 333 │ BigCo Codes     │ contract-58-idp-u… │ BigCo Codes │ managed     │       │     │ Yes    │ 15        │       │
    │    │ Contract           │                    │                │             │       │     │        │              │       │
    └────┴────────────────────┴────────────────────┴────────────────┴─────────────┴───────┴─────┴────────┴──────────────┴───────┘
    ```
4. Add the courseware: `./manage.py b2b_courseware add 333 course-v1:UAI_SOURCE+A.0001x`
5. Get the enrollment codes: `./manage.py b2b_list contracts --codes 333`
   The codes will be written to a file called `codes-333.csv`.

**Result:**

In MITx Online:

1. A new organization should be created and should show up in `b2b_list organizations`
2. A new contract should be created and should show up in `b2b_list contracts`
3. The course should be added to the contract, which you should be able to see in `b2b_list courseware`.
4. 15 enrollment codes should have been created.

In edX:

1. A new course run should exist, with key `course-v1:UAI_BIGCO+A.0001x+2025_Cxx` (where 2025 is the current year, and Cxx is C and the contract ID).

After logging in as a user:

1. The user account should be not be attached to anything, and should see nothing within their Learn dashboard relating to the org or contract.
2. They should be able to use an enrollment code to gain access.
   1. They can use the link that is provided in the enrollment code CSV file, which will enroll them in the course as well.
   2. They can use the enrollment code at `/enrollmentcode/<code>` on Learn, which will add them to the contract.
3. Once they've used the code, they should see the org and course in Learn.
   1. If they used the `/enrollmentcode` URL, they will see "Start Module".
   2. Otherwise, they should see "Continue Module."
4. The learner should be a member of the organization in Keycloak.
5. Once the learner logs out and back in, the organization membership listed in their account in MITx Online should _not_ have the "keep until seen" flag set. It will have it set immediately after the code is used, though.
