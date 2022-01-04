Release Notes
=============

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

