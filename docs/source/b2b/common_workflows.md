# Common Workflows

These are some common workflows for the B2B system that can be used verbatim or as a template or guide to operation.

## Prerequisites

You'll need at least one course with a designated source course run.

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

## UAI contract with enrollment codes

## Single-course B2B contract
