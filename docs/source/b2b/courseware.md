# Courseware Resources

The ultimate goal of the B2B system is to provide course offerings to the organizations that we're partnering with. To that end, we have some special processes and considerations for courses intended for B2B contracts.

## Background

MITx Online and edX have some necessary disagreement about the terms used for course resources. The main disconnect is with the concept in courses and course runs.

* A **course** in edX is an optionally time-limited course offering that contains enrollments. Learners work within a course and can earn certificates within it.
* In MITx Online, a **course** is a container. Courses contain many **course runs** which represent individual instances of the course that learners can take, and have enrollments and certificates.

So, a MITx Online **course run** is analogous to an edX **course**. We have this structured as it is because we need to have a single entry point for a "course" so that it can have a marketing page and to handle multiple simultaneous runs of the same course.

MITx Online also has the concept of a **program**, which is a collection of courses with requirements to complete the program. edX doesn't have any analogue for a program.

It is also important to have some familiarity with a **course key**. A course key is a particular type of [_opaque key_](https://github.com/openedx/opaque-keys), and an opaque key is a standardized identifier for various different kinds of object within edX. (They're used for everything from an edX course as a whole to individual blocks within the course.) In MITx Online, we _generally_ refer to these as either `readable_id` or `courseware_id`. Opaque keys follow a particular format that the course key builds upon and the parts of the key are important when considering B2B-associated courses.

A course key has this format: `course-v1:OrgCode+CourseNumber+RunTag`. An example of an actual key is `course-v1:MITxT+18.01.3x+2T2025` (Calculus 1C: Coordinate systems and infinite series). This breaks down as such:
- Key is a course key (`course-v1`)
- The course belongs to the MITxT organization (`MITxT`)
- The course number is 18.01.3x (`18.01.3x`)
- The run tag is 2T2025 (`2T2025`) which represents the second semester in 2025

The key identifier doesn't change. The organization, course number, and run tag all change according to the needs of the course. B2B courses have some conventions that we use for these fields:

- The organization is set according to the course's "owner". We construct this using some system data.
    - For UAI courses, it's always prefixed with `UAI_`. For B2B courses, it's prefixed with `B2B_` or may not be prefixed.
    - The organization slug is then appended. So, for UAI courses within the MIT organization (where the slug is "MIT"), the organization is `UAI_MIT`.
- The course number is something reasonable for the course.
- The run tag represents either the contract and year it was created for, or a special value for source runs.
    - For a course that belongs to a contract in a particular organization, the run tag is `Cx_yyyy`, where `x` is the contract ID and `yyyy` is the year it was created. (So, for contract 102 in year 2025, this would be `C102_2025`.)
    - For a source course run, this is `SOURCE`.

In MITx Online, we use a course key to identify the MITx Online course as well as the course run. However, it's important to know that, because edX _doesn't_ have separate courses and runs, there's also not a specific key format for this use case. We simply use the course key without the run tag. This is technically an invalid key but it only makes sense within MITx Online.

## Courses and B2B Runs

Creating and running a course within MITx Online is typically a pretty linear operation. A course offering is developed and run as a course run. MITx Online gets a course record and the first course run from that. Once the course completes, we re-run the course for each semester that we want to offer the course. The main things that change (from MITx Online's perspective) are the run tag and the course dates. We do allow some course runs to continue indefinitely as a self-paced course, and those courses may have time-limited instructor-led runs that run simultaneously.

For B2B courses, runs are more chaotic. Each contract requires its own course run for each course that's associated with the contract - we do not generally allow intermingling between learners in separate contracts or in other organizations. So, we may have any number of course runs for a given course in progress at the same time. Additionally, we don't necessarily develop course content specifically for a given contract - we often have a B2B-ready offering that we make available. (We may make some org or contract specific changes in the runs for those, but the bulk of the content does not change.)

### Source Course Run

To facilitate this, we have the concept of a "source course run". The source run is a regular course run. We use the "source" run as the base run for all B2B-associated offerings that we need to create.

MITx Online's course run model has a flag that designates a course run as a source course run. When adding courseware to a particular contract, the source run flag comes into play:
- If an MITx Online course is added to a contract, the system checks for any existing runs that have the source flag set. The system uses the source run to create a re-run of the course in edX for the contract.
- If an MITx Online program is added, the system loops through the requirements tree for the program and adds the individual courses as if they were specified manually.

When a source run is re-run for a given contract, we change some of the details about the new course run:
- The organization part of the key is changed to represent the contract's organization. Ex: a `UAI_SOURCE` organization would become `UAI_MIT`.
- The run tag is changed to represent the contract and year the run was created, as described above.

_It's important to note that, even though the organization part of the key changes, the course still belongs to the same MITx Online course._ In other words, if we re-run `course-v1:UAI_SOURCE+12.345x` - which has a source run, `course-v1:UAI_SOURCE+12.345x+SOURCE` - for a contract in MIT, we'll end up with a run called `course-v1:UAI_MIT+12.345x+C99_2023`. But, it will still be in the MITx Online hierarchy under `course-v1:UAI_SOURCE+12.345x`.
