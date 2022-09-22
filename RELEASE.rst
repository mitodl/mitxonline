Release Notes
=============

Version 0.45.6
--------------

- fix: product discount calculation for inactive product on course detail page (#1026)
- added user info to sync_enrollment and updated sentry config to pass send_default_pii

Version 0.45.5 (Released September 21, 2022)
--------------

- Bump google sheets versions
- Adds a management command to create a basic financial assistance form for a courseware object
- Fix (#1018)

Version 0.45.4 (Released September 21, 2022)
--------------

- fix: text change to OFAC disclaimer (#992)
- Adds an email message that is sent when an order is refunded

Version 0.45.3 (Released September 20, 2022)
--------------

- data migration for certificate index page (#974)
- fix(deps): pin dependencies

Version 0.45.2 (Released September 20, 2022)
--------------

- fixed the link to the flexible pricing form on the course detail popup
- Fix factory-boy package name and pin
- Fixing test - forcing Decimal type and limiting calced amount to 0
- chore(deps): update actions/checkout action to v3
- chore(deps): update dependency attrs to v22
- chore(deps): update codecov/codecov-action action to v3
- chore(deps): update actions/cache action to v3
- chore(deps): update actions/setup-python action to v4
- display certificate start and end date on template (#973)
- Versioning of certificate template (#903)

Version 0.45.1 (Released September 19, 2022)
--------------

- fixed course/program filter for flexible pricing request
- Fix renovate config
- Add renovate.json5
- updated justifications based on action for flexible pricing requests in refine admin
- feat: Add command for certificate management (#897)
- Adding list_display for FlexiblePriceAdmin (#971)
- 942: unauthorized user can access staff dashboard (#969)
- added course/program filter to flexible pricing request on dashboard
- added legacy grades migration, updated enrollment
- Updates product pages to allow for price widget display based on flexible pricing submission and status; added some helper stuff for calculating discounted amounts for arbitrary products
- Adds a refresh button to the Flexible Pricing Request list page in staff dashboard

Version 0.45.0 (Released September 14, 2022)
--------------

- design tweaks on order/product/dashboard pages
- 842: sync-coursrun-upgrade-deadline-with-edx (#919)
- Adds a check to make sure flexible pricing forms have the right fields in them
- Online-941 Filter zero value discounts on checkout (#958)
- Online-943 Update course start string (#946)

Version 0.44.0 (Released September 09, 2022)
--------------

- Fix failing test_order_refund_success_with_ref_num (#948)
- Refund order based on id or reference number (#847)
- fix external checkout by passing course_id
- add is_self_paced to MicroMaster courserun import script
- fixed dashboard doesn't refresh when user unenrolls from course in program
- Adds a feature flag (overridable by URL) for the program UI
- Adds accessibility attributes to make the program drawer work better with screen readers
- Wraps the check for a course page and certificate page in a try/except so it doesn't fail if there's no course page for the courserun enrollment
- Dashboard course card UI updates (#926)
- Adds info text at the bottom of the course about pages for OFAC messaging

Version 0.43.0 (Released September 07, 2022)
--------------

- fix: certificate error when end_date is not set (#923)
- Hide description if certificate is also hidden (#922)
- Program Flexible Pricing approval page (#917)
- feat: poll grades and generate certificates (#722)
- updated color contrast on dashboard
- 905: dashboard overflow menu ⋮ accessibility (#908)
- Added queries to migrate order/line/transaction from MicroMaster
- fixed migration conflicts and discount tests
- Fixes nav issues with a course date is selected
- 884: dashboard design update (#888)
- added unique keys to ecommerce line/transaction
- add error log for transactions' reason code any number other than 100
- fix: basket checkout with zero value (#899)
- Adds setup command to bootstrap financial aid for DEDP
- Learner and anonymous certificate view- issue #692 #693 (#892)

Version 0.42.1 (Released August 31, 2022)
--------------

- Update flexible pricing approval email to eliminate errors when sending
- Adds currency code descriptions; makes sure invalid codes are removed
- Get certificate at reduced price (#856)
- 872: checkout remove clear discount and a few other tweaks (#877)

Version 0.42.0 (Released August 25, 2022)
--------------

- Fixes some issues with the Fastly API code
- Ecommerce: adds activation and expiration dates to discount codes
- Adds additional fields to the course API
- fix: active products to cart only (#874)
- Online-868 Hide enrolment button for anonymous users (#875)
- Check for program page before checking for child pages (#878)
- 811: need financial assistance link on the checkout page (#855)
- 806: ecommerce implement a cybersource notification api endpoint (#817)
- added css and js to remove incremantal arrow for income field
- Online-860 Calculate flexible price discount instead of using BasketDiscount (#861)
- Adds text to display when a flexible pricing request is assigned a $0 tier
- Purges the Fastly cache for a page once the page has been modified

Version 0.41.2 (Released August 19, 2022)
--------------

- fix: datetime issue in flexible price form (#863)
- feat: Add Certificate Template using Wagtail CMS (#740)
- feat: add course run upgrade deadline (#820)
- Online-841 Adds support for Financial Assistance Request denied email (#851)
- Online-839 Improve Financial Assistance Request List View (#845)
- Adds program pages to the CMS
- Bump django from 3.2.14 to 3.2.15 (#824)
- Online-843 Fix import and reset state bugs for financial assistance (#844)
- Online-829 Open program drawer when program title is clicked (#846)
- Update (#835)
- Online-815 Fix styling for income field (#833)

Version 0.41.1 (Released August 17, 2022)
--------------

- Fixes some conditionals to return good values if there's no CMS page for a courseware object
- Online-664 Show courseware and discount info for a financial assistance request (#796)
- online-779 Display `Documents in order` as default (#781)
- Adding an extra retry and extending startup grace period to 45s; should help with starting up on Apple Silicon

Version 0.41.0 (Released August 12, 2022)
--------------

- Fixes scrolling within the program drawer
- altered unique_object_id_validated to include content_type
- added  program tier mapping table, financial aid migration query
- Remove learners tab from staff dashboard
- More Dates: Tooltip title text, style, irrelevant dates bug fixes #767 (PR #798)
- added reference_number to Order model, backfill
- Updates flexible pricing to add a unique constraint on submissions
- Adds program support to the dashboard
- Updates status filtering to make it clearable
- Switch some settings to use urljoin
- Updated ecommerce docs to include max product price and unique CVN (#785)
- added migration queries to migrate MicroMaster courserun and enrollment
- Adds explicit binding of flexible price request forms to courseware objects
- Add a scheduled task to process_refund_requests (#773)
- altered course_run.run_tag to textfield with max_length 100
- Restrict single active product per course ID (#774)
- online-778 Order flexible prices by most recent first (#782)
- fix flow
- linting issue
- JS linting fix
- More dates for course enrollment
- 734 - registration validate username against openedx (#757)
- Updates "skipped" to "denied" in flexible pricing
- Updates courses API to explicitly create ProgramEnrollments when enrolling in a course
- 770 - flexible pricing: too many decimal places (#772)
- online-677 Indicate Financial Assistance links if available for a course (#764)
- Added backfill migration for new table paid courserun

Version 0.40.1 (Released August 04, 2022)
--------------

- fix: enrollment upgrade from free to paid version (#763)

Version 0.40.0 (Released August 02, 2022)
--------------

- fix: protect Product model from deletion (#753)
- added validation to prevent duplicated payment for paid courserun
- 751-flexible-pricing-remove-thank-you-page (#755)
- online-709 Financial Assistance: Update Financial Assistance Request Form (#718)
- added a tracking table for course run purchases
- Cleaning up some old unused imports
- Refactored action modal into its own component
- Added an error toast if the justification isn't set, updated mutation code to set state properly before mutating
- Reworked some of the state logic; using the antdesign Select rather than a bare html select

Version 0.39.6 (Released August 01, 2022)
--------------

- Add data models and command to import MM data
- Adding Google Sheets Refunds functionality to mitxonline (#723)

Version 0.39.5 (Released July 28, 2022)
--------------

- Use count instead of total from the API response (#752)
- 728: flexible pricing learner cant resubmit income after request has been denied reset (#746)
- Flexible pricing clean up email template (#743)
- Bump moment from 2.29.2 to 2.29.4 (#712)

Version 0.39.4 (Released July 27, 2022)
--------------

- Adds code to group course run enrollments by program

Version 0.39.3 (Released July 26, 2022)
--------------

- Adds support for tying a discount to a specific product
- Flexible pricing display personalized price (#720)
- Updating docs to add in path to the file you need to edit for lms settings

Version 0.39.2 (Released July 26, 2022)
--------------

- This is to adapt to a bug, that should be fixed later
- Flexible Pricing approved requests should apply to programs
- Bump lxml from 4.6.5 to 4.9.1 (#666)
- Move enabled, add default credentials/base URL
- Make suggested changes

Version 0.39.1 (Released July 25, 2022)
--------------

- Revert "Update steps for accessing and configuring devstack"
- feat: refund orders CyberSource - Integrate [mitol-django-payment-gateway] (#599)
- Add instruction to define edx base url
- Update steps for accessing and configuring devstack
- Revert "Update steps for accessing and configuring devstack"
- Update steps for accessing and configuring devstack
- Use master branch and don't clone mitodl edx

Version 0.39.0 (Released July 19, 2022)
--------------

- update the design for the flexible pricing request form (#689)

Version 0.38.0 (Released July 18, 2022)
--------------

- Adds flexible pricing flag to Discount objects
- fixes a typo ("you will find a copy of youR receipt"); adds a slash that got removed due to local config
- Adds order ID to the data that gets sent to the receipt email
- Adds healthcheck to watch and refine containers; makes refine "depend" on watch
- Remove missing section link
- OrderHistory and OrderReceiptPage to PrivateRoute
- Flexible Pricing: email notifications should be sent when statuses change
- Removes the Status inline filter (since there's another one); makes the Find Records box horizontal

Version 0.37.1 (Released July 13, 2022)
--------------

- fix(warning): use StreamFieldPanel instead of FieldPanel (#662)
- Bump django from 3.2.13 to 3.2.14 (#661)

Version 0.37.0 (Released July 07, 2022)
--------------

- Revert "Flexible Pricing: email notifications should be sent when statuses change"
- Sends email notifications when Flexible Pricing request statuses change
- asadiqbal08/Dropdown Justification is not maintaining the state after refresh (#632)
- Reworked the test a bit so it doesn't fail
- Updated refine configuration docs for deploys
- - format on ReceiptPageDetailCard - Moves the NotificationContainer inside the Header component and adds flexbox styling so alerts logically appear before the header (and are thus read first by screen readers)
- Capture learner's country when saving flexible pricing request
- Updated country_of_residence to be blankable
- Updated receipt sending stuff to parse order created date (was being passed as a string, not a datetime, and broke the filter); updated email copy

Version 0.36.2 (Released June 29, 2022)
--------------

- Add never_cache() decorator to react views
- Updated build system so refine builds for deploys
- Updates copy on Forgot Password and Email Verification screens
- Bump pyjwt from 2.1.0 to 2.4.0 (#588)
- Adds management command to find possible username conflicts
- If a coupon is entered it should replace the financial aid discount only if it's a higher discount. (#630)
- Moved orderHistory route and reworked it so it renders properly

Version 0.36.1 (Released June 22, 2022)
--------------

- feat: update cart to handle products from external checkout (#626)
- Fixes: Receipt page is empty when there is no discount code (#621)
- Show justification once status changed (#622)
- Adds Order History to the top menu
- Updates mitol-django packages
- Changing coupon code label to "Coupon code" from "Have a code?"

Version 0.36.0 (Released June 17, 2022)
--------------

- asadiqbal08/A button to deny the flexible pricing request (#611)
- flexible pricing should be applied automatically when a course is added to the cart (#614)
- Refactored menu and dialog toggles to be simple booleans
- formatting, adding verification modal tests
- Updating wording on dialog
- Added modal that is displayed when a user tries to unenroll from a certificate course

Version 0.35.0 (Released June 10, 2022)
--------------

- Cleanup and simplify configuration/localdev

Version 0.34.0 (Released June 09, 2022)
--------------

- asadiqbal08/Added Approve and Reset button to Refine Admin (#603)
- Flexible Pricing: Automatically approve if the Learner is elligible when they request it (#580)
- Adjust styles of Refine dashboard to be more MIT
- Adds free-form text searching and status searching to Refine admin for flexible pricing records
- Updated docker-compose to pull some stuff out of .env file, updated data source to use .env for base URI
- load currency exchange rate (#590)

Version 0.33.0 (Released June 06, 2022)
--------------

- asadiqbal08/Updated the Receipt Page with additional Details (#578)
- Adds a check for exchange rate description when constructing the currency list
- Adds Flexible Pricing list view to Refine admin
- Added documentation for configuring the Refine Admin

Version 0.32.2 (Released May 31, 2022)
--------------

- Adds custom email receipts to the ecommerce system

Version 0.32.1 (Released May 24, 2022)
--------------

- Removed call to save_and_log; VersionAdmin takes care of history tracking

Version 0.32.0 (Released May 23, 2022)
--------------

- Adding flexibile pricing request form functionality

Version 0.31.1 (Released May 20, 2022)
--------------

- Adding status flags, Get Certificate button to dashboard
- add financial aid models to admin and load country income thresholds (#563)

Version 0.31.0 (Released May 17, 2022)
--------------

- Adds check for product to Enroll button logic
- Added heroku deployment workflows

Version 0.30.2 (Released May 17, 2022)
--------------

- Reworked generateStartDateText to avoid short circuiting
- Bump django from 3.2.12 to 3.2.13 (#535)
- refactored out start date text generation elsewhere, added test for that, fmt caught some other stuff too
- Refactoring out EnrolledItemCard
- Adding discounts to the Refine Admin
- fix course ordering on the dashboard (#546)

Version 0.30.1 (Released April 29, 2022)
--------------

- fixes courses display incorrect date on the dashboard (#538)
- fixes ecommerce accessibility discount code error message is invisible to screen reader (#526)

Version 0.30.0 (Released April 28, 2022)
--------------

- fix video on course page is not screen reader accessible (#520)

Version 0.29.0 (Released April 21, 2022)
--------------

- Adding administrative discount APIs
- Fix tests on CI

Version 0.28.0 (Released April 21, 2022)
--------------

- fix ecommerce accessibility coupon code field has no label (#521)
- Porting flex pricing models from MicroMasters

Version 0.27.0 (Released April 20, 2022)
--------------

- Added refine admin

Version 0.26.0 (Released April 14, 2022)
--------------

- Adding back yarn workspaces

Version 0.25.1 (Released April 07, 2022)
--------------

- Documentation updates post-ecommerce

Version 0.25.0 (Released April 06, 2022)
--------------

- Revert "Add support for yarn workspaces"
- Add support for yarn workspaces
- Fixing Paid tag display on checkout page
- Adjusts tests to make them more reliable

Version 0.24.4 (Released April 06, 2022)
--------------

- Fixing some issues with order history/receipt views
- Display refund/paid tags on orde receipts
- refactor: use youtube controls for youtube videos (#491)
- styling changes - moving the main breakpoint from md to lg (see #493)
- added error method to errorable Order states, fixed isLoading on cart page to actually work

Version 0.24.3 (Released March 31, 2022)
--------------

- Adding pagination to order history page
- Bump pillow from 8.3.2 to 9.0.1 (#473)

Version 0.24.2 (Released March 28, 2022)
--------------

- Adds logic to avoid stepping on an in-progress basket when processing checkout responses
- Check for blocked countries during checkout (#477)

Version 0.24.1 (Released March 23, 2022)
--------------

- Adding code to handle refunding orders

Version 0.24.0 (Released March 23, 2022)
--------------

- Accessibility: Bypass Blocks: bypass the header on site pages for screen readers (#463)

Version 0.23.2 (Released March 18, 2022)
--------------

- fix email unsubscription inconsistency after unenrollment (#475)

Version 0.23.1 (Released March 16, 2022)
--------------

- Adding OrderReceiptPage (#449)

Version 0.23.0 (Released March 14, 2022)
--------------

- Fix cart total display when no discounts are applied
- Adding transaction_type field
- Account for baskets that end up being zero-value after discounts
- Adding Discount UI

Version 0.22.0 (Released March 08, 2022)
--------------

- Adding migration to update enrollment modes to default to audit

Version 0.21.0 (Released March 07, 2022)
--------------

- fixing privacy policy link
- Only show the upgrade sidebar if upgrade ui enabled
- Support enrolling learner as verified on payment
- Adding UX tweaks, upsell card
- unsubscribe from course emails after unenroll (#416)
- Adding order history page

Version 0.20.5 (Released February 25, 2022)
--------------

- Fixing wrapping issue with long course titles (#426)

Version 0.20.4 (Released February 24, 2022)
--------------

- Fixed 500 and 404 error pages
- Updating payment_gateway to 1.2.2, fixing some usage errors with said library
- Add url to add product to the cart and redirect.

Version 0.20.3 (Released February 23, 2022)
--------------

- Adding checkout page UI
- Add Upgrade Enrollment Dialog

Version 0.20.2 (Released February 17, 2022)
--------------

- Added feature flag to enable/disable the test checkout UI
- allow to unenroll even after the enrollment period has past (#404)

Version 0.20.1 (Released February 15, 2022)
--------------

- Removing import for turtle in models
- Adds CyberSource integration and checkout APIs

Version 0.20.0 (Released February 15, 2022)
--------------

- Bump django from 3.2.11 to 3.2.12 (#405)

Version 0.19.4 (Released February 09, 2022)
--------------

- Bump wagtail from 2.13.4 to 2.15.2 (#383)

Version 0.19.3 (Released February 08, 2022)
--------------

- Bump django from 3.2.10 to 3.2.11 (#372)

Version 0.19.2 (Released February 01, 2022)
--------------

- Format code since `black` changed regex flag order 🙄

Version 0.19.1 (Released January 31, 2022)
--------------

- Bump ipython from 7.24.1 to 7.31.1 (#382)

Version 0.19.0 (Released January 26, 2022)
--------------

- fix: add the requirements for mitol-django-openedx (#389)
- Basket Subsystems API (#370)
- fix email settings pop-up references wrong course (#380)
- Revert "Revert "Change unsubscribe UI to email settings (#375)" (#381)" (#385)
- Bump celery from 4.3.0 to 5.2.2 & celery-redbeat to 2.0.0 (#363)
- Revert "Change unsubscribe UI to email settings (#375)" (#381)
- Change unsubscribe UI to email settings (#375)
- style: style: add support footer (#371)
- fix: replacing course key with course number in enroll and unenroll email (#333)
- Sort courses on home page by date ascending (#368)
- feat: Allow users to unsubscribe from course emails from the dashboard (#329)
- Adding discount abstractions

Version 0.18.3 (Released January 06, 2022)
--------------

- Added Product subsystem REST API
- Order models
- Add black formatting check to CI

Version 0.18.2 (Released January 06, 2022)
--------------

- docs: fix broken open edx config link (#356)
- feat: add search index for readable id (#352)

Version 0.18.1 (Released January 04, 2022)
--------------

- fixing auto named migration
- updated migration after black run
- forgot to run black
- Addded Discount, UserDiscount, DiscountRedemption models
- Addded Discount, UserDiscount, DiscountRedemption models
- Documentation updates

Version 0.18.0 (Released January 04, 2022)
--------------

- Bump lxml from 4.6.3 to 4.6.5 (#335)

Version 0.17.1 (Released December 23, 2021)
--------------

- fix: enable dashboard course link when end date is in past (#349)
- Bump django from 3.2.5 to 3.2.10 (#334)
- removed unused code
- formatted course name and ordered them in explorer
- Adding Basket subsystem models (#338)

Version 0.17.0 (Released December 22, 2021)
--------------

- Added autofocus and tabindex properties to div (#328)
- Revert "Adding Basket subsystem"
- Adding Basket subsystem
- Ran formatter on admin.py
- Updated products model admin bindings to include reversion hook Updated main config to include reversion (forgot to do this earlier) You will need to migrate and run createinitialrevisions (per the django-reversion docs)
- ran formatter on new code
- migrated object list into a function
- removing unused stuff
- Added app for ecommerce, Products model, admin bindings

Version 0.16.2 (Released December 07, 2021)
--------------

- removed docker-node file
- updated task name
- asadiqbal08/ Fix accessibility issue by tabindex to header (#286)

Version 0.16.1 (Released December 02, 2021)
--------------

- Strengthen validation requirements for course pages (#318)

Version 0.16.0 (Released November 30, 2021)
--------------

- fix the build

Version 0.15.0 (Released November 29, 2021)
--------------

- Fixing: 'Enroll now' button appears when 'Enrollment start' date is in the future (#282)

Version 0.14.1 (Released November 23, 2021)
--------------

- added ol-django-authentication app to MITxOnline

Version 0.14.0 (Released November 18, 2021)
--------------

- Fixed tooltip behavior when enrollment period is active
- Course product pages: If no Video URL is set, display the Feature Image (#300)
- upgrade to yarn 3
- Bump django from 3.2 to 3.2.5 (#291)
- Bump validator from 10.11.0 to 13.7.0 (#285)
- Upgrade to django 3.2 (#196)
- Removed @ symbol as valid username character
- Use SVG for the MIT logo (#281)
- Prevented unenrollment for runs with expired enrollment period
- Load enrollment status dynamically in product detail page (#255)

Version 0.13.2 (Released November 17, 2021)
--------------

- Course product pages: If no Video URL is set, display the Feature Image (#300)

Version 0.13.1 (Released November 15, 2021)
--------------

- Fixed Heading font sizes

Version 0.13.0 (Released November 01, 2021)
--------------

- Added unenroll button to dashboard

Version 0.12.4 (Released October 28, 2021)
--------------

- removed unused depedencies and imports

Version 0.12.3 (Released October 20, 2021)
--------------

- Show dates, times, and time zones on dashboard (#254)

Version 0.12.2 (Released October 19, 2021)
--------------

- fix: remove multiple instances loading of polyfill (#248)

Version 0.12.1 (Released October 07, 2021)
--------------

- bump webpack-bundle-tracker=0.4.3 to fix deep-extend alert (#230)
- Fixed user notifications so they are only seen once

Version 0.12.0 (Released October 04, 2021)
--------------

- Added username whitespace trimming and case-insensitive unique validation
- fix product detail spacing issues (#226)

Version 0.11.2 (Released October 04, 2021)
--------------

- Added headers to tab order
- build: upgrade sentry browser and sdk version + RedisIntegration (#232)
- Fixed product detail links to in-progress enrolled course runs

Version 0.11.1 (Released September 30, 2021)
--------------

- Fixed dashboard card spacing and image sizing

Version 0.11.0 (Released September 29, 2021)
--------------

- Bump django from 3.1.12 to 3.1.13 (#213)
- fix retry_edx_enrollment management command (#209)
- Fixed 'enrolled' UI regression

Version 0.10.0 (Released September 27, 2021)
--------------

- Removed username from profile edit form

Version 0.9.1 (Released September 24, 2021)
-------------

- Fixed logged-out bug on product detail page

Version 0.9.0 (Released September 23, 2021)
-------------

- Fixed logout link
- Fixed 'enrolled' UI on product detail page
- Allowed admins/editors to access closed edX courses (#190)
- Update product description help text in CMS (#201)
- Fixed accessibility issues in forms
- Bump sqlparse from 0.4.1 to 0.4.2 (#181)
- Bump pillow from 8.3.1 to 8.3.2 (#158)
- Fixed profile and auth UI

Version 0.8.0 (Released September 21, 2021)
-------------

- Add privacy policy and terms of service links to register page (#198)
- fix: address accessibility concerns on Dashboard and Product Detail Page (#176)
- fix migration conflicts (#203)
- add help_text in courserun title and dates for syncing from edX studio course (#195)
- Implemented user-supplied usernames

Version 0.7.1 (Released September 20, 2021)
-------------

- fix: resolve the accessibility issues in header (#168)
- Pull courserun title, dates from studio (#166)
- Enable no cache for API
- Implemented country blocklist at the course level
- Added valid mitx logo (#182)

Version 0.7.0 (Released September 14, 2021)
-------------

- Fixed user menu visibility regression
- Updated Forgot Password flow in case of email does not exist. (#169)
- Added enrollment sync when dashboard loads

Version 0.6.0 (Released September 13, 2021)
-------------

- made forgot password case insensitive
- Added loading animation component and applied to dashboard

Version 0.5.1 (Released September 10, 2021)
-------------

- fix user name font weight in user menu (#165)
- fix head title for wagtail based pages (#152)
- fix: accessibility issues on homepage (#160)
- improve top-bar menu (#135)
- Added welcome message for users that complete first authentication
- Fixed CMS migrations, added startup command to configure Wagtail

Version 0.5.0 (Released September 08, 2021)
-------------

- add/enable GTM support for basic events (#140)
- update empty dashboard message (#144)
- changed background color
- asadiqbal08/Move prerequisites (#126)
- asadiqbal08/Don't link to courses that aren't open yet (#139)
- asadiqbal08/Add support for the default Feature Image (#128)

Version 0.4.2 (Released September 07, 2021)
-------------

- updated styles for Create Account and Sign In Pages
- enhance footer layout design (#129)

Version 0.4.1 (Released September 01, 2021)
-------------

- Remove settings regarding reloading worker processes (#133)
- fix: styling and layout changes for dashboard, footer and product page (#98)

Version 0.4.0 (Released August 31, 2021)
-------------

- Bump path-parse from 1.0.6 to 1.0.7 (#82)
- Made entire course card clickable
- add dashboard, rename settings in the topbar menu (#124)

Version 0.3.4 (Released August 30, 2021)
-------------

- Update openedx configuration docs
- make product page faculty memebers optional (#122)
- Fixed animation issue and overlay open/close issue
- added embeded video in product page
- Added setting to avoid name collisions in Wagtail

Version 0.3.3 (Released August 20, 2021)
-------------

- Fixed issues with register API and recaptcha (#111)

Version 0.3.2 (Released August 20, 2021)
-------------

- Implemented enrollment and notification from product detail

Version 0.3.1 (Released August 19, 2021)
-------------

- add faculty section in the product page (#89)

Version 0.3.0 (Released August 17, 2021)
-------------

- allow dot in course readable_id (#85)
- Fixed home page product URLs
- Added course index page

Version 0.2.1 (Released August 13, 2021)
-------------

- fix home page feature products section (#88)
- changed image src to valid image
- fix: made dashboard accessible only when authenticated (#77)
- home page product section (#38)

Version 0.2.0 (Released August 11, 2021)
-------------

- Implement logged-ui in the site header (#54)
- Fixed container class  styling
- Added API endpoint for creating user enrollments
- Added styling to pin footer to the bottom of the page
- Added dashboard message for users with no enrollments
- fix wagtail media upload error (#66)
- added styling for header logo and sinin/creat account links (#37)
- Removed unneeded auth fields
- asadiqbal08/Basic Product Detail Page (#45)
- add header hero section details (#48)

Version 0.1.1 (Released August 05, 2021)
-------------

- fix the regex length issue for forgot-email api
- Implement resource pages and links from site footer (#36)

Version 0.1.0 (Released August 04, 2021)
-------------

- Implement basic site footer content (#41)
- Cleaned up stale references to xpro in docs
- Added minimal learner dashboard
- Fix flaky util test
- Add courses app
- Added Wagtail and initial model definitions

