# Course Customization Support

MITx Online supports customized runs for courses. B2B contracts also support customizations; in this context, the contract indicates which customizations are desired by the customer.

Customizations require some additional setup for course, course run, and contracts. The course needs to know what customized runs _should_ exist, the contract needs to store what the customer wants, and the course runs need to be set up to indicate what options they were built to support.

The system supports three kinds of customizations:

- Language: Course content has been translated in its entirety into the specified language.
- Industry Focus: Course content has been adapted to focus the subject matter onto a specific industry.
- Length: Course content has been adapted for length, utilizing either short-form video summaries or other methods.

Industry and Length customizations are typically not used for publicly-available course runs, but this is not disallowed.

The system also supports marking a given set of customization options as "B2B only", which applies the set only to B2B course runs.

A set of customization options is referred to as a **variant**. That term will be used for the remainder of this guide.

## Defaults

We expect a default variant - this maps to the traditional single course run that we usually have for a course. While the default variant can be set up in whatever way is required for the course, the _standard_ default is:

- Language: English (`en`)
- Industry: None (blank)
- Length: Full (blank)

Only one default variant set is allowed per course.

## Course Setup

Courses all contain a list of _supported variants_. These are the kinds of customized runs that _should_ exist for the course. Runs that are customized in ways that aren't represented in the course won't show up in API results, so they'll be effectively invisible from the system. (They can still be made, though - sometimes, having these runs be hidden is a feature and not a bug.)

To set up variants for a course:
- Pull up the course from within the Django Admin. The Supported Variants are listed at the end of the page.
- Set the options as appropriate. You can add new ones, or adjust existing ones.
- Save the course.

After configuring a course's variants, use the `check_courseware_variant` management command to see if a given course is set up properly, and see what runs exist that match the variants that are supported as well as what runs exist that don't. It also accepts a flag, `--fix-default`, which will create the standard default variant (English and no length/industry) for the course.

:::{note}
If you have a variant that should be supported by _both_ the public and by B2B contracts, you need to add it to the course _twice_, once with the "B2B-only" flag checked and once without. Otherwise, the variant will _only_ apply to one type of run or the other.
:::

:::{note}
The default flag overrides the B2B-only flag - a variant marked as default is supported for both B2B contracts and the public.
:::

## Course Run Setup

Once the variants are configured, course runs need to be either created, imported, or updated to match the variant definitions.

:::{important}
It is not **required** that all variants are covered by a course run, but it is expected. If there's no course run fitting the definition of a specific variant, the default run will be used instead, which may be confusing to users (especially if the only variation is language).
:::

To update the variant settings for a given course run:
- Pull up the run within the Django Admin. (Hint: the Course view now shows a list of runs for the course, and includes links to open the Course Run.)
- Under Customization Variant, set the fields as appropriate.
- Save the course run.

After making changes to course run variant options, it's a good idea to run the `check_courseware_variant` management command to make sure things are as expected.

If you are **importing** a course run, the `import_courserun` command includes `--length`, `--industry`, and `--language` options for the imported run. Be advised that the command _cannot_ decipher these options from the edX course data, and it will _not_ create variants in the course for you. It will warn you if you've chosen options that aren't supported, though.

### Course Run Groupings

It's important to know how course runs are grouped into logical runs.

In essence, we still offer access to courses as before - we have a distinct run of a given course that either occurs between a set start date and end date, or that is marked as self-paced and optionally allows access at a given starting point. These runs are still designated with a run tag within MITx Online, and historically we've only allowed a run tag to be used once on a course run within a given course.

Courses with customized content work in the same way: we still offer the course as a run that has a particular set of dates and pacing settings. We now also offer those runs with a range of customization options, because the customized courses are all offered at the same time with the same parameters. So, now the run tag also encompasses the customized offerings. Each customized offering needs to be its own separate course run within edX, so the run tag is used to group all of these runs together logically.

> For example: we may offer a course - `course-v1:MITxT+92.345` - in its original language of English, but also in French, Chinese, and Arabic, so the course is configured with 4 variants. The next scheduled offering of the course is for `3T2026`, so we will have 4 course runs with run tag `3T2026` - one each for each supported language. (However, since these all need to be distinct within edX, the run tag _there_ will be more like `3T2026_en` or `3T2026_zh`.)
>
> If the industry or length options are set, the same procedure happens - we continue to use the same run tag (`3T2026`) in MITx Online, so that all the courses are grouped together there, and the edX course run's run tag is amended as necessary. So, for the above course in Chinese, with Short videos and industry focus on Healthcare, the run tag _in edX_ would be `3T2026_zh_S_HC` or similar.

We have added some database checks to help keep the data manageable and enforce these groupings. You can only have one run that has a set of language, industry, and length options per combined set of course, run tag, source course flag, and B2B contract.

These groupings ensure the UI works and that learners have options that make sense when they choose a variant.

### Creating Unsupported Variants

You can set the variant fields to whatever values make sense for a given run. However, these runs won't show up in Learn unless there's a matching variant set up in the course. This may be advantageous in some situations - the runs can be created in MITx Online and then effectively hidden from view until the variant is configured.

Variants have an "active" flag - making a variant inactive will have the same effect as deleting it, so building out a new set of variants can be done by building out the support in MITx Online and leaving the variant itself inactivated until the course content is ready to go live.

## Contract Setup

Contracts also contain a list of variants, which are the _requested_ variants for the contract. Adding these follows the same process as setting variants up for a course, except:
- The interface for the contract variants is in the Django Admin. (We will add a Wagtail interface for variants but that hasn't been completed yet.)
- The "B2B Only" flag is ignored, as contracts are always B2B-only.

Contracts also have a management command for checking the variant setup - `check_contract_variant` - and it works in much the same way as the courseware version.

:::{note}
The `check_courseware_variant` command also has a `--contract` flag - this will show you what B2B variants are configured for the course and what the matching course runs _may_ be. (It pulls contract runs, matched up against the _course_ variants, and displays them grouped together with the course's B2B variants.)
:::

### Source Courses and Variants

When adding a course to a contract - either directly or via a program - the system will try to make a new run for the course, based on the source course that is available. This process takes into consideration configured variants as well. So, source course runs for each configured variant _must_ exist to be able to offer the variant within the contract, in addition to having the variant configured in the course and contract themselves.

This also means that numerous contract runs may be created for a single course. Unless told otherwise, the `b2b_courseware add` command will create a new run for each contract variant that has a corresponding course variant. So, using the example from the Course Run Groupings section above, adding `course-v1:MITxT+92.345` to a contract would result in 4 runs being created, assuming the contract and course variant lists matched and there were source runs for each variant.

As noted, the _course_ variants need to have the "B2B only" flag set to True for the variant to apply to this process (unless it is the default variant). If the sample course only specified French and Arabic as B2B-only, then the Chinese run would be skipped, even if the contract requests it.

The `b2b_courseware add` command has a `--variant` flag to limit which variants are applied to a contract. When using this flag, note that _all_ required variants must be specified, including the default. The command will assume you want only the specified things if you're using the `--variant` flag.
