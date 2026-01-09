Flexible Pricing
================

The Flexible Pricing system allows learners to request alternative pricing for MITx Online courses based on their location and annual income. These requests can be made through a customizable form in the Wagtail CMS system.

Flexible pricing is based on the learner's location and annual income. Several tiers of pricing can be available based on these factors. Requests must be approved and may require additional documentation be submitted via DocuSign. Approval indicates that the form has been submitted and processed, but may not guarantee a reduced price (e.g., sufficient income may put users in a "No discount" tier.) Denial indicates an issue processing the request.


Requirements
*************

For flexible pricing to function properly, you will need several records in the system, mostly generated via management commands. These can be added before or after the flexible pricing form, but APIs will not function properly until they are added.

- **Exchange rates**: ``./manage.py update_exchange_rates`` (requires ``OPEN_EXCHANGE_RATES_APP_ID``, which can be taken from RC.)
- **Income thresholds**: ``./manage.py load_country_income_thresholds flexiblepricing/data/country_income_thresholds.csv``
- **Courseware**: Courses with course runs and, optionally, a program (See ``create_courseware`` and ``create_coursewage_page`` management commands)
- **Products**: Products associated with course runs.

  - For courses in a program, you can create products for each course run via ``./manage.py create_product_for_program_courses --program <program_readable_id>``; add ``--active`` to ensure the products are active.
  - For standalone courses, create a product for the courserun manually via Django Admin.

- **Flexible Pricing Form:** See below.
Form Creation
*************

Flexible pricing forms are managed in Wagtail and can be children of either a course or a program. To create a flexible pricing form, use the ``create_finaid_form`` management command then modify the form as needed. Alternatively, you can manually add the form as a child page in Wagtail.

**The create_finaid_form management command**: Run ``./manage.py create_finaid_form <courseware_readable_id> [--force]``. This will:

1. If the courseware is a program, add the form as a child of the program page.
2. If the courseware is a standalone course:

   - If the course does NOT belong to a program, add the form as a child of the course page.
   - If the course DOES belong to a program, add the form as a child of the program page, **unless** the ``--force`` option is specified. In that case, the form will be under the course page.

**Manually Adding the Form:** To manually add the form, navigate to the course or program page in Wagtail (click the page itself; do NOT click the pencil icon, which will edit the page itself). Then, click the "Add Child Page" button on the courseware page and select "Flexible Pricing Request Form." (Do NOT click the pencil icon).

**Editing the created form:** The wagtail form includes:

1. *Form Fields*: This are auto-generated when the form is published.
2. *Text Customization:*

   1. The Intro field text is displayed on the form regardless of the state of the request.
   2. The Guest text is displayed if the learner isn't logged in yet.
   3. The Application Processing text is displayed if the learner navigates to the form again and their application is still being processed.
   4. The Application Approved text is displayed if the learner navigates to the form and their application has been approved.
   5. The Application Approved No Discount text is displayed if the learner navigates to the form and their application has been approved, but they've been approved for a zero-value tier. (In other words, the learner has exceeded the upper limit of flexible pricing.)
   6. The Application Denied text is displayed if the learner navigates to the form and their application has been denied.

Submitting and Approving the Flexible Pricing Request
*************

The flexible pricing request form is linked to on relevant course and program pages.

After a user submits a request, a ``FlexiblePrice`` record will be created for the user. The price is initially in a "Pending" status and must be approved manually. Approval can be done via Django Admin or the Refine staff dashboard.
