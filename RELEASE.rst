Release Notes
=============

Version 0.93.2
--------------

- can we just do this? (#2208)

Version 0.93.1 (Released May 14, 2024)
--------------

- 4111: dashboard crashes when user profile is incomplete (#2206)

Version 0.93.0 (Released May 13, 2024)
--------------

- Give priority to enrollable runs (#2198)
- Add task for creating featured items in cache (#2203)

Version 0.92.1 (Released May 10, 2024)
--------------

- restrict duplicate enrollment only if user is verified (#2199)
- add relational dates to ensure all courses end up getting pulled (#2200)

Version 0.92.0 (Released May 09, 2024)
--------------

- Adding a Learn More link to Archived message (#2194)
- Adding management command and function for pulling featured items (#2190)
- Course format pacing info popup (#2187)
- Remove redux-asserts (#2177)
- Remove react-swipeable (#2178)
- chore(deps): update all non-major dev-dependencies (#2171)
- fix(deps): update dependency redux-asserts to v0.0.12 (#2168)

Version 0.91.1 (Released May 06, 2024)
--------------

- 4137: mitx online course and program count on catalog page is incorrect in mobile view (#2186)
- warning message (#2188)
- Update duplicate enrollment meassage (#2184)
- fix: Resolve Poetry lock file
- fix: Resolve failing pre-commit check
- fix: Resolve minor pre-commit fixes
- chore(deps): lock file maintenance (#2185)
- Pre commit linting (#2161)
- Update dependency react-hot-loader to v4.13.1 (#2166)
- Update dependency enzyme-adapter-react-16 to v1.15.8 (#2163)
- Update poetry and yarn lock files (#2183)

Version 0.91.0 (Released May 02, 2024)
--------------

- 4012: Improve screen reader accessibility of the site-wide banner. (#2180)
- Add course format and new wording for course box info (#2175)
- Update dependency object.entries to v1.1.8 (#2164)
- Update dependency postcss to v8.4.38 (#2165)
- Update dependency ubuntu to v22 (#2039)
- Update dependency reselect to v4.1.8 (#2169)

Version 0.90.1 (Released May 01, 2024)
--------------

- Updating the styles and adding test for course with no runs (#2172)
- Update dependency style-loader to v3.3.4 (#2170)

Version 0.90.0 (Released April 25, 2024)
--------------

- Adding end date info to the CourseInfoBox (#2160)
- Update akhileshns/heroku-deploy digest to 581dd28 (#1196)
- Course Product Page with no Runs (#2157)
- Fix: Add nubbins for celery monitoring. (#2159)

Version 0.89.2 (Released April 16, 2024)
--------------

- Fix catalog page for empty app (#2152)
- Fix enrollment dialog default option (#2154)
- Form error messages should appear consistently and be accessible  (#2151)
- change route to catalog from root now that we have a catalog (#2155)
- Ensure filteredPrograms is set earlier and change the route when navigation changes. (#2153)

Version 0.89.1 (Released April 09, 2024)
--------------

- Enrollment request make sure not enrolled (#2149)
- Deferrals: set to audit instead of unenrolling (#2146)

Version 0.89.0 (Released April 04, 2024)
--------------

- Add URL routing for catalog for courses/programs and department (#2140)
- 3005: adding a banner snippet in the header that appears on every page of the site (#2144)
- fix(deps): update dependency express to v4.19.2 [security] (#2145)
- 3649 all mitxonline courses should have a department (#2132)
- Upgrade enrollment dialog fixes (#2141)
- Showing Course rather than Courses (or program/s) when there is only 1 to display (#2139)
- Distinguish change forms in account settings (#2142)
- fix(deps): update dependency webpack-dev-middleware to v5.3.4 [security] (#2138)
- Upgrade dialog choose any course run (#2124)

Version 0.88.1 (Released March 20, 2024)
--------------

- Updates to ancillary pages (#2119)
- remove extraneous console.log statement (#2131)
- 1257: updating meta tags on mitx online site (#2128)

Version 0.88.0 (Released March 20, 2024)
--------------

- Fetch by department when selected (#2120)

Version 0.87.4 (Released March 18, 2024)
--------------

- 3360: on account registration redirect new users to the page they started on (#2127)

Version 0.87.3 (Released March 13, 2024)
--------------

- 2846 Course About: Replace Free with Free to Learn (#2125)

Version 0.87.2 (Released March 07, 2024)
--------------

- Change program end date to certificate creation date (#2121)

Version 0.87.1 (Released March 07, 2024)
--------------

- adding enrollment change tracking (#2117)
- 3689: add department filter to the api endpoints for courses and programs (#2118)

Version 0.87.0 (Released February 29, 2024)
--------------

- Fix mobile counts on catalog (#2114)

Version 0.86.3 (Released February 22, 2024)
--------------

- Change the callback to respond on programs page as well (#2111)
- Certificate Page: End date should be certificate creation date (#2110)

Version 0.86.2 (Released February 21, 2024)
--------------

- Create certs only for live programs (#2108)
- fix course card not keyboard accessible issue (#2105)
- Update dependency pytest to v6.2.5 (#2106)

Version 0.86.1 (Released February 15, 2024)
--------------

- Admin improvements to CourseRunEnrollmentAudit model (#2103)
- Accessibility: updating intructors info (#2101)

Version 0.86.0 (Released February 14, 2024)
--------------

- Fix the width of course image (#2099)
- Program certificate for different program types (#2096)
- Updating favicon (#2097)
- Program courses cards styles (#2095)
- Lock file maintenance (#2042)
- Update dependency wagtail to v5.2.3 (#2088)
- Update dependency video.js to v7.21.5 (#2087)
- Update dependency pylint-django to v2.5.5 (#2085)
- Update dependency pylint to v2.17.7 (#2084)
- Update dependency django-redis to v5.4.0 (#2086)
- Update dependency django to v3.2.23 (#2083)

Version 0.85.3 (Released February 05, 2024)
--------------

- New MITxOnline Logo (#2074)
- Fix for program unenrollment modal (#2081)
- 2075: some dialogs email settings unenroll not keyboard navigable (#2079)
- Fixes use of "redemption_type" when generating discount codes in bulk, fixes test error (#2077)
- Wrapping product creation in a create_version block so versions happen like they should (#2073)
- Catalog: sorting courses and programs by title (#2071)

Version 0.85.2 (Released January 24, 2024)
--------------

- Update Publish Documentation to newer versions of stuff so it runs (#2070)
- Updated fixed price test to be less flaky (#2069)

Version 0.85.1 (Released January 23, 2024)
--------------

- Fix program id retrieval when sharing (#2061)

Version 0.85.0 (Released January 22, 2024)
--------------

- 3382: self paced courses with future start dates show start anytime (#2066)
- 3400 remove enrolled state and modal default (#2065)
- Removes instances where we've feature flagged the new (current) design (#2064)
- Delay alert when rendering the page in order to engage screen reader alert (#2059)
- 3362: No opacity on program card, pointer when hovering (#2062)
- Show More link on product about page accessibility (#2063)
- Update react-redux and related packages to facilitate catalog changes (#2030)

Version 0.84.0 (Released January 18, 2024)
--------------

- Explain Course Formats (#2054)
- check if departments have been defined (#2057)
- fix flow (#2053)
- Remove role menu (#2043)
- fix(deps): update dependency ipython to v8 (#2036)

Version 0.83.0 (Released January 09, 2024)
--------------

- add next parameter to course and program enrollment pages for unauthenticated users (#2050)
- display course number on program enroll modal (#2048)

Version 0.82.4 (Released January 04, 2024)
--------------

- When resolving the current run, make sure it's also enrollable (#2046)

Version 0.82.3 (Released January 03, 2024)
--------------

- Check to make sure the end date and upgrade deadline haven't passed before grabbing your audit enrollment (#2044)
- fix(deps): update dependency posthog to v3.1.0 (#2032)
- Program enrollment: choose courses (#2028)
- fix(deps): update dependency boto3 to v1.34.5 (#1803)
- Update dependency enzyme-adapter-react-16 to v1.15.7 (#1806)
- Update dependency chai to v4.3.10 (#1804)
- Update dependency celery to v5.3.6 (#2029)
- Update dependency @sentry/browser to v6.19.7 (#1802)
- Update dependency @craco/craco to v6.4.5 (#1801)
- chore: Bump Python patch release and generate Poetry lock (#2041)
- Update dependency dayjs to v1.11.10 (#1805)
- Update dependency postcss to v8.4.31 [SECURITY] (#1943)

Version 0.82.2 (Released December 14, 2023)
--------------

- add styles to the navbar on product page (#2020)
- Certificate: using product title (#2024)
- Updating the program enrollment  dialog text (#2025)
- Filter out courseruns that can't be upgraded when displaying the upsell dialog (#2023)
- Make department sidebar sticky on mobile (#2015)

Version 0.82.1 (Released December 06, 2023)
--------------

- Fixes course run selection code and standardizes it (#2017)
- Fixes the keyboard trap issue with instructor modals (#2019)
- Accessibility: tabbing through featured products improvement (#2018)

Version 0.82.0 (Released December 04, 2023)
--------------

- Wraps the program cards (which are in a `ul`) in a `li` tag (#2013)
- Mobile redesign: add course and program counts (#2011)
- Accessibility: make CourseInfoBox discoverable (#2010)
- Accessibility: Make label visible to screen reader (#2004)
- Catalog Page: updating header and list elements (#2005)

Version 0.81.0 (Released November 29, 2023)
--------------

- Fix just the counts from Catalog (#2008)
- Announce course count change (#2006)
- Updates CSS to add hover states on the program course cards (#2007)
- Departments v2 endpoint - now with more course and program counts (#1997)
- Reoder product info for mobile view (#1999)

Version 0.80.2 (Released November 20, 2023)
--------------

- Updates the onclick for the instructor name to activate on keyup, fixes an issue with financial assistance page serialization (#2001)
- Adding "text-break" so the browser will break long words into lines if it has to (#2000)
- If the FA form is for a different program, pull that program's page URL as the root rather than the one we've been asked for (#1998)
- Headings for required courses start date (#1995)
- Product Page: Display none for hidden text (#1996)

Version 0.80.1 (Released November 14, 2023)
--------------

- Fixes start date formatting in CourseInfoBox, refactors date display for reuse (#1992)

Version 0.80.0 (Released November 14, 2023)
--------------

- Header nav links fixes (#1988)

Version 0.79.5 (Released November 13, 2023)
--------------

- Change Catalog to use v2 API endpoint for courses (#1987)
- Adding breadcrumb navigation and program type badge (#1981)
- Updated v1 course API to only pull live programs; added tests (#1989)
- Add page__live filter to programs API and update url in catalog page query (#1990)

Version 0.79.4 (Released November 08, 2023)
--------------

- Adding a test for archived courses (#1985)
- Adds v2 of the courses API for the program page (#1983)

Version 0.79.3 (Released November 08, 2023)
--------------

- Change urls to not break (#1982)
- Fixing date to display if you're logged in (#1979)
- Update header design and navigation (#1969)
- Removing final vestiges of clickable more dates selectors (#1977)

Version 0.79.2 (Released November 02, 2023)
--------------

- Update how we call the posthog API to include another person identifier to allow for easier targetting (#1973)
- Fixing the mobile styling on the enrollment modal (#1975)
- Course About Page: tablet and mobile view adjustments (#1960)

Version 0.79.1 (Released November 02, 2023)
--------------

- Enrollment dialog WCAG fixes (#1965)
- Change Catalog Page to use the new v2 programs endpoint (#1971)
- Programs API v2 (#1966)
- Instructor bio cards styles (#1967)
- Updated get_financial_assistance_form_url to also consider related programs (#1940)

Version 0.79.0 (Released October 30, 2023)
--------------

- Program API test updates (#1963)
- Instructor popup modal mobile view (#1961)
- Course API test updates (#1962)

Version 0.78.0 (Released October 23, 2023)
--------------

- Course About Page: update font and styles (#1957)

Version 0.77.1 (Released October 23, 2023)
--------------

- Catalog Page: Mobile view changes (#1956)

Version 0.77.0 (Released October 18, 2023)
--------------

- Filter out not live programs (#1954)
- Product Page: about section Show More toggle updates (#1949)
- Course Page: More enrollment dates updates (#1951)
- wsgi tuning setup config (#1947)

Version 0.76.1 (Released October 11, 2023)
--------------

- Product Page: Fix overflow on faculty info boxes (#1945)
- Remove start date from ProgramInfoBox.js (#1938)
- Course About Redesign - Accessibility issues on instructor bio (#1942)

Version 0.76.0 (Released October 05, 2023)
--------------

- Catalog Page: Add content loader  (#1941)
- don't leak grades in program record before course completed (#1931)

Version 0.75.6 (Released October 03, 2023)
--------------

- Revert "Assorted fixes for More Dates selector in existing design" (#1937)
- Carousel Fixes (#1935)
- Fix start date test on course info card (#1932)
- Course Product Page: show more enrollment dates (#1925)
- somehow lost this logic (#1927)

Version 0.75.5 (Released September 28, 2023)
--------------

- Assorted fixes for More Dates selector in existing design (#1903)

Version 0.75.4 (Released September 28, 2023)
--------------

- Update course info bar to respond to archived courses (#1923)

Version 0.75.3 (Released September 26, 2023)
--------------

- Course Calatog: Stay on selected department (#1921)

Version 0.75.2 (Released September 26, 2023)
--------------

- Fix Duplicate Courses on Catalog Page (#1920)

Version 0.75.1 (Released September 26, 2023)
--------------

- Add FAQ cert link and prerequisites to product_page.html (#1917)
- Fix product page (#1915)

Version 0.75.0 (Released September 25, 2023)
--------------

- Hide programs tab when department has none (#1914)

Version 0.74.4 (Released September 25, 2023)
--------------

- Self paced dates -> start any time (#1911)

Version 0.74.3 (Released September 21, 2023)
--------------

- Skip courses if they don't have a published CMS page (#1907)

Version 0.74.2 (Released September 20, 2023)
--------------

- Re-add the fix from PR 1900 to the reworked product page components (#1909)
- Catalog page css updates - v1 (#1891)

Version 0.74.1 (Released September 20, 2023)
--------------

- New design: adds program page (#1833)
- User dropdown menu updates (#1899)

Version 0.74.0 (Released September 19, 2023)
--------------

- Swap posthog to use js sdk with minimal settings (#1904)

Version 0.73.3 (Released September 19, 2023)
--------------

- Updates the code behind the More Dates selector to work without the course page (#1900)
- Add courses api filters to catalog page (#1892)
- change z index for hero to make it stop sitting over dropdown (#1897)
- Issue#2382 (#1894)
- footer css updates for mobile landscape screen (#1890)
- Updates create_courseware to allow you to specify departments (optionally creating them) (#1887)
- Fixes to  Featured Carousel (#1889)
- Video Component Styling fix (#1875)
- Course passed if has course run certificate (#1878)
- Use site name variable (MITx Online) for page title (#1888)
- Updating video player CSS to work better in the new design (#1883)

Version 0.73.2 (Released September 13, 2023)
--------------

- Repair cart page including reinstated course api improvements (#1885)
- Revert "Department REST API (#1877)" (#1882)
- New design footer css updates (#1881)
- Add new header design (#1873)
- Department REST API (#1877)

Version 0.73.1 (Released September 12, 2023)
--------------

- 1869: Course program api performance improvements (#1872)
- Remove duplicate catalog URL path (#1871)

Version 0.73.0 (Released September 11, 2023)
--------------

- Change fonts to new correct fonts for home page (#1866)
- Redesign footer (#1868)

Version 0.72.0 (Released September 11, 2023)
--------------

- Updates the course about page CSS (#1865)
- remove non-standard issue templates (#1716)
- Home Page Contact Component (#1853)
- add outer overlay + style desktop and mobile (#1863)
- fix profile validation and regex error (#1848)
- fix expandable Read More 500 error (#1861)

Version 0.71.0 (Released September 06, 2023)
--------------

- uncaught merge issue on fixing the previous issue (#1859)
- Posthog refactor  (#1857)
- 1845: Remove unused feature flag and import (#1847)
- 1842: duplicate ProductPage get_context method in model (#1846)
- use contenthash not chunkhash (#1792)
- Fix background css on feature flagged areas (#1840)
- made a session variable for anonymous user for the purpose of posthog tracking (#1841)
- Moving home-page files, pulling out unnecessary imports from styles.js and meta-product-page (#1838)
- Home Page Video Component (#1828)
- Home Page Hero Component (#1826)
- New extended certificate generation window (#1832)
- 1676 design new catalog page (#1818)
- Fixes text alignment for the Enrolled button, hide the upsell card in new design (#1830)
- Featured Products Carousel (#1820)
- New design: Course page layout changes (#1816)

Version 0.70.9 (Released August 23, 2023)
--------------

- update full name on user profile (#1825)
- When deferring enrollment set to verified (#1790)
- Update to Enrolled in certificate track label to count for audit enrollment with certificates (#1823)

Version 0.70.8 (Released August 17, 2023)
--------------

- feat: add ability to retire users on edX (#1785)

Version 0.70.7 (Released August 16, 2023)
--------------

- Changes template to display long bio, adds migration to move short bios to long, updates management command to fill short bio with something else to prevent confusion (#1812)
- Adds the PostHog settings to the JS settings so we can use it in React. (#1814)
- Add posthog to repo (#1809)

Version 0.70.6 (Released August 15, 2023)
--------------

- feat: force all enrollments (#1761)

Version 0.70.5 (Released August 08, 2023)
--------------

- Forgot to actually retrieve the course (#1807)
- Instructions for updating python dependencies with poetry (#1800)

Version 0.70.4 (Released August 03, 2023)
--------------

- Use poetry for python dependency management (#1766)
- remove assertRaises
- remove unncessary momentjs locales

Version 0.70.3 (Released August 01, 2023)
--------------

- Populate passing DEDP grades that were set to None by Admin (#1787)

Version 0.70.2 (Released July 31, 2023)
--------------

- Migrate instructor data to individual selectable pages (#1786)
- Updates to the dashboard functionality (#1756)
- Deferrals better message (#1776)
- Manage certificates command: require letter grades when overriding grade (#1767)

Version 0.70.1 (Released July 26, 2023)
--------------

- Fixing amounts for the default tiers for the configure_tiers command (#1782)
- Add program_type field to database (#1778)

Version 0.70.0 (Released July 26, 2023)
--------------

- Program records: show verified grades or grades with certificate (#1775)

Version 0.69.2 (Released July 24, 2023)
--------------

- Updates import_course a bit for program requirements (#1760)
- 1764: Ignore ordering in tests where it doesn't matter (#1765)

Version 0.69.1 (Released July 20, 2023)
--------------

- 1758: Django Admin course validation for Program nested elective operators (#1759)
- Sheets functionality and usage description (#1735)
- 1694: added stipulations to program electives causes 500 error in Django admin (#1751)
- No audit grades in program records (#1747)

Version 0.69.0 (Released July 18, 2023)
--------------

- Populate letter grades for 3T2022 (#1754)
- add migration to delete duplicate discount redemption

Version 0.68.0 (Released July 17, 2023)
--------------

- ProgramSerializer should now return default image if there's no program page (#1750)
- 1740: Re-enroll learner into program (#1746)
- feat: remove link and add description for unenrollable runs in more dates (#1684)

Version 0.67.6 (Released July 13, 2023)
--------------

- Updates the discount redemption cleanup code to be more resilient (#1748)

Version 0.67.5 (Released July 12, 2023)
--------------

- Update procfile - add hubspot task queue to normal worker dyno
- Refactors serializers/views for speed in enrollment APIs, adds flag to designate requirements as electives or not (#1736)
- 1718: improve hubspot bulk update database queries (#1731)
- Add hubspot_sync celery task queue specifically for hubspot related tasks (#1733)

Version 0.67.4 (Released July 10, 2023)
--------------

- Refund Order should return propper error message (#1726)

Version 0.67.3 (Released July 06, 2023)
--------------

- Adds support for featured images in programs (#1724)

Version 0.67.2 (Released July 06, 2023)
--------------

- Add unverify option to google sheets plugin (#1717)

Version 0.67.1 (Released July 05, 2023)
--------------

- Clears discounts when reusing an existing PendingOrder (#1721)

Version 0.67.0 (Released July 05, 2023)
--------------

- add migration to fix letter grade set by 0033
- update letter_grade for MM grade, add missing enrollment import script
- Refund Order: remove atomicity and rollback (#1706)

Version 0.66.2 (Released June 28, 2023)
--------------

- 1702: line serializer cannot handle orders with no current enrollment (#1703)
- 1691: program certificate generation does not adhere to nested program electives (#1707)

Version 0.66.1 (Released June 28, 2023)
--------------

- Merging migrations from #1708 and #1704 (#1709)
- Optimize program enrollments API (#1708)
- fix courses migration conflict (#1704)
- Convert grade into letter for program records (#1651)
- update migration to use apps.get_model
- fix format
- Add course readable ID to courses in program requirement admin UI
- fix bug on renderCourseInfoCard, add migration to backfill certificate enrollments

Version 0.66.0 (Released June 28, 2023)
--------------

- Fixes the course count on cards in My Programs (#1690)
- Remove program field from course model (#1685)
- 1664: management command to create Order from enrollment (#1674)

Version 0.65.10 (Released June 13, 2023)
---------------

- Update google-sheets-refunds/deferrals (#1676)

Version 0.65.9 (Released June 13, 2023)
--------------

- Format the merge of PR 1670 (#1677)
- Handle enrollment for users with multi pendorder (#1670)
- Delete PR Template

Version 0.65.8 (Released June 12, 2023)
--------------

- Adding date checks to Discount model (#1672)

Version 0.65.7 (Released June 08, 2023)
--------------

- Handle HubSpot exceptions when unenrolling from a course (#1667)
- Handle un-enrollment prior to audit enrollment Order creation feature (#1663)
- 904: tracking audit enrollments for mitx online courses in hubspot (#1644)

Version 0.65.6 (Released June 07, 2023)
--------------

- Updating refund_order API to check for PayPal (#1655)

Version 0.65.5 (Released June 07, 2023)
--------------

- 703: navigation drawer component not screen reader accessible round 2 (#1653)

Version 0.65.4 (Released June 07, 2023)
--------------

- Fix hook bug in sheets refunds (#1657)

Version 0.65.3 (Released June 06, 2023)
--------------

- Adds normalization for edX profile fields (#1650)
- Make deferral functionality atomic and clarify errors (#1641)

Version 0.65.2 (Released June 05, 2023)
--------------

- Updates the email address on the frontend to use the value from settings. (#1645)
- fix format issue
- add management command to create local enrollments from edx

Version 0.65.1 (Released May 31, 2023)
--------------

- Adds bulk code generation to staff-dashboard (#1631)

Version 0.65.0 (Released May 30, 2023)
--------------

- update google-sheets-deferrals (#1637)
- Incorporates changes to make MITxOnline work with Tutor (#1376)
- Add row header to order history table (#1636)
- Remove scheduled cron task (#1635)
- Working (#1632)
- Adding google sheets deferrals library (#1604)

Version 0.64.1 (Released May 25, 2023)
--------------

- 1627: improve hubspot sync script to handle large numbers of users (#1628)
- Expands edX profile sync, adding gender, year of birth, and level of education fields
- Bump cookiejar from 2.1.3 to 2.1.4 (#1373)

Version 0.64.0 (Released May 23, 2023)
--------------

- update mitol/hubspot_api app (#1624)
- chore(deps): update dependency cachetools to v4.2.4 (#1611)
- Bump dns-packet from 5.3.1 to 5.4.0 (#1460)

Version 0.63.26 (Released May 15, 2023)
---------------

- Fix flexible pricing page for programs (#1616)

Version 0.63.25 (Released May 15, 2023)
---------------

- Revert "1605: get certificate button on approved flexible price leads to empty cart (#1609)" (#1613)

Version 0.63.24 (Released May 15, 2023)
---------------

- Find user by account email not social auth email (#1610)
- Use new hubspot_api version and try to sync contacts individually if a batched sync chunk fails (#1607)
- 1605: get certificate button on approved flexible price leads to empty cart (#1609)
- Update Wagtail to v5 (#1606)

Version 0.63.23 (Released May 09, 2023)
---------------

- Changes the login workflow to ignore case in the email field (#1600)
- Removes a stray aria-hidden attribute (#1602)
- config: Update renovate config

Version 0.63.22 (Released May 03, 2023)
---------------

- 1573 sync extended profile data to hubspot (#1579)
- chore(deps): update dependency django-anymail to v9 (#1581)

Version 0.63.21 (Released May 03, 2023)
---------------

- Bump redis from 3.5.3 to 4.4.4 (#1519)
- Bump http-cache-semantics from 4.1.0 to 4.1.1 (#1407)

Version 0.63.20 (Released May 02, 2023)
---------------

- Add AR Argentina (#1584)
- Fixes us_state to return None if there's no state; adds a test for that (#1589)
- Throw an error if the user manages to get to the registration screen with the same email (#1586)

Version 0.63.19 (Released May 01, 2023)
---------------

- Updates fields that are sent to edX and adds profile sync (#1578)

Version 0.63.18 (Released May 01, 2023)
---------------

- Update decode uri component from 0.2.0 to 0.2.2 (#1582)
- chore(deps): update dependency certifi to v2022 [security] (#1271)
- chore(deps): update dependency sqlparse to v0.4.4 [security] (#1568)
- Update requests package (#1558)

Version 0.63.17 (Released April 26, 2023)
---------------

- Reverts the page title on the additional details page (some debug code that slipped through) (#1576)

Version 0.63.16 (Released April 25, 2023)
---------------

- Updating legal address validation to check state validity only if specified (#1574)

Version 0.63.15 (Released April 25, 2023)
---------------

- chore(deps): update dependency cryptography to v39 [security] (#1421)

Version 0.63.14 (Released April 24, 2023)
---------------

- 1566: align price on upsell card (#1569)
- Removes call to forcibly set addl_field_flag from frontend (#1563)

Version 0.63.13 (Released April 24, 2023)
---------------

- Upsell card, Set bg-danger to lighter red (#1564)
- Order History Page table makeover (#1535)

Version 0.63.12 (Released April 20, 2023)
---------------

- 1295: learner menu stops functioning at a particular width range (#1561)

Version 0.63.11 (Released April 20, 2023)
---------------

- Update "right" and "left" to "end" and "start" (#1559)

Version 0.63.10 (Released April 20, 2023)
---------------

- Fix program record page, no required courses (#1556)
- 1549: Fixes program record with null nodes and no children with tests (#1554)

Version 0.63.9 (Released April 13, 2023)
--------------

- Update badges to bootstrap v5 (#1550)

Version 0.63.8 (Released April 12, 2023)
--------------

- 715: ecommerce pressing pay jumps back to dashboard without focus on alert (2) (#1544)
- Fix (#1546)
- fix: remove codecov because it's gone from PyPI, the codecov action would do it anyway (#1545)
- 715: ecommerce pressing pay jumps back to dashboard without focus on alert (#1537)

Version 0.63.7 (Released April 11, 2023)
--------------

- 1538 users are still able to log in using a retired email account/login error messages (#1539)

Version 0.63.6 (Released April 06, 2023)
--------------

- 1522: Remove instances of ErrorMessage for required fields (#1526)

Version 0.63.5 (Released April 05, 2023)
--------------

- 123: remove use of aria-hidden and aria-live on dashboard (#1532)
- Update references to MITx Online (#1530)

Version 0.63.4 (Released April 04, 2023)
--------------

- Improvement (#1528)
- fix: management command for deferring users with course mode (#1517)
- Bump oauthlib from 3.2.1 to 3.2.2 (#1417)

Version 0.63.3 (Released April 03, 2023)
--------------

- Add aria-label to apply button (#1523)
- validate edit profile form on submit (#1521)

Version 0.63.2 (Released April 03, 2023)
--------------

- Reworks extra fields form to compress things so the modal fits above the fold on smaller viewports. (#1518)
- 1508: screen readers should not pronounce * ("star") for labels (#1515)

Version 0.63.1 (Released March 27, 2023)
--------------

- 1104: Perform validation on year of birth field during registration (#1505)
- accessibility improvements for dashboard and drawer (#1504)
- Removing unnecessary alt texts from images (#1503)

Version 0.63.0 (Released March 27, 2023)
--------------

- Requests additional information from the learner when they register. (#1499)

Version 0.62.9 (Released March 20, 2023)
--------------

- Resolve issue when repairing user's edx synchronised records (#1496)

Version 0.62.8 (Released March 20, 2023)
--------------

- fix and tests (#1491)
- feat: sync certificate_available_date with edX (#1478)

Version 0.62.7 (Released March 15, 2023)
--------------

- Adjust discount redemption checks to only consider orders in Fulfilled state for validity
- Bump webpack from 5.71.0 to 5.76.0 (#1488)

Version 0.62.6 (Released March 15, 2023)
--------------

- Course page 500 error for expired course runs and flex price (#1486)

Version 0.62.5 (Released March 13, 2023)
--------------

- Allows verified learners the ability to unenroll; adjusts flow for refunds (#1474)

Version 0.62.4 (Released March 13, 2023)
--------------

- fix: retry_failed_edx_enrollments should check for existing enrollments (permission fix) (#1479)
- fix: Fix program admin to add a new program (#1477)
- 1473: duplicate enrollment emails (#1475)
- 977: allow enrollment in archived courses (#1472)
- fix: retry_failed_edx_enrollments should check for existing enrollments (#1458)
- Declining an order should now clear redemptions associated with the order; added test for this (#1471)
- Adds a typeError to the state field validation to suppress the default yup error (#1470)
- 1455: Adds templatetag for noindex in non-prod (#1468)

Version 0.62.3 (Released March 08, 2023)
--------------

- feat!: remove `Course.position_in_program` (#1429)
- Changes refund_order to let exceptions bubble up, and removes duplicate as a successful result (#1463)

Version 0.62.2 (Released March 06, 2023)
--------------

- Moves Highest Level of Education field up (#1462)

Version 0.62.1 (Released March 02, 2023)
--------------

- Fixing a call to `set_rollback` that was incorrect

Version 0.62.0 (Released March 02, 2023)
--------------

- Adds additional demographic fields to the system; adds popup to collect more data when visiting a course

Version 0.61.4 (Released February 28, 2023)
--------------

- Updated configure_tiers to work with courses as well as programs
- Adding command for manually "refunding" the user's enrollment (#1451)
- fix: limit user full name to 255 characters (#1440)

Version 0.61.3 (Released February 23, 2023)
--------------

- Fixes some issues with validation for new profile fields; adds extended profile fields (#1443)

Version 0.61.2 (Released February 23, 2023)
--------------

- Updates the command to include the enrollment mode when running enroll_in_edx_course_runs (#1444)
- fix: sync_enrollments command error message and exit (#1442)
- Adds year of birth, gender, and a conditional state field to the user profile (#1436)

Version 0.61.1 (Released February 16, 2023)
--------------

- Adds methods to check pending orders for resolution through CyberSource (#1423)
- Bump django from 3.2.15 to 3.2.18 (#1431)

Version 0.61.0 (Released February 15, 2023)
--------------

- fix: Fix flexible pricing generic relations (#1412)
- feat: Add discount payment types (#1390)

Version 0.60.0 (Released February 09, 2023)
--------------

- Log any exception thrown by hubspot task helpers (#1416)
- feat: Move orders to canceled if transaction is reviewed (#1419)
- Updates enrollments to regenerate auth tokens if they're invalid
- Updates enrollment upsell dialog to immediately create enrollments (#1410)
- Fix and tests for undefined program course nodes (#1408)
- Fix for heading and description height (#1409)

Version 0.59.1 (Released February 07, 2023)
--------------

- feat: Sync courseware title with CMS page title (#1382)
- Bump ua-parser-js from 0.7.31 to 0.7.33 (#1394)
- Bump terser from 5.12.1 to 5.16.2 (#1406)
- Update readme (#1405)
- fix: Fix edX username validation to avoid username collision (#1389)
- Add a workflow for new issues

Version 0.59.0 (Released January 30, 2023)
--------------

- Updates program certficiate text

Version 0.58.2 (Released January 26, 2023)
--------------

- Fix (#1391)

Version 0.58.1 (Released January 25, 2023)
--------------

- Removes the ENABLE_LEARNER_RECORDS feature flag. (#1375)
- feat: add search and filters on Discount admin model (#1381)
- 1346 learner record UI improvements (#1368)
- Update README.md (#1369)
- Updates repair_faulty_edx_user to reconnect edX users (#1371)

Version 0.58.0 (Released January 24, 2023)
--------------

- Makes it easier to cancel an order in the Review state (#1367)
- Updates discount application code to strip whitespace
- feat(import_courserun): add ability to block countries (#1352)
- fix: Fix program learner record when there is no grade (#1364)
- Only display course number (#1345)
- Removed check for values before rendering the create discount form (#1361)
- fix: show only published/live product pages on home page (#1356)
- fix: Fix admin search for redeemed discounts (#1359)

Version 0.57.1 (Released January 24, 2023)
--------------

- Retry Hubspot API calls on 429 errors (#1334)
- Use on_commit in signal to avoid trying to sync a product to hubspot before it has been saved to the db (#1351)
- Updates discounts in the staff dashboard to reflect the current state of the art (#1324)
- fix: incorrect output from manage_certificates command when auditing (#1355)
- Bump pillow from 9.0.1 to 9.3.0 (#1231)
- Bump json5 from 1.0.1 to 1.0.2 (#1322)
- feat: unenroll without a refund (#1333)

Version 0.57.0 (Released January 12, 2023)
--------------

- Removing feature flag for program UI; small styling change to My Courses tab (#1311)
- fix: Display course passed tag based on course dates and pacing (#1317)

Version 0.56.5 (Released January 12, 2023)
--------------

- Fix: Program courses drawer won't open if program has no elective or required courses (#1338)

Version 0.56.4 (Released January 11, 2023)
--------------

- 1326: decimal grades on the learner record (#1331)
- add the row back for formatting (#1332)
- Program Drawer: remove enroll button (#1314)

Version 0.56.3 (Released January 09, 2023)
--------------

- fix: 404 enrollment not found (#1323)
- Updates manage_certificates to handle revoked certificates better (#1320)
- Hubspot integration (#1313)
- Bump @xmldom/xmldom from 0.7.5 to 0.7.9 (#1216)
- Bump ejs from 3.1.6 to 3.1.8 (#1201)
- Bump loader-utils from 1.4.0 to 1.4.2 (#1217)
- Fixing command to fix get_or_create call (#1307)
- Fixes the course model to round the grade - this was causing a test failure (#1299)
- fix:dashboard confirmation dialog for unenrolling from courses (#1301)

Version 0.56.2 (Released January 03, 2023)
--------------

- Revert "Removes feature flag; small styling adjustment on My Courses tab when no Programs tab"
- Removes feature flag; small styling adjustment on My Courses tab when no Programs tab
- fix: don't show programs tab if user isn't enrolled in a program (#1303)
- Update course message if already enrolled (#1300)

Version 0.56.1 (Released December 21, 2022)
--------------

- fix: Fix courseware URL in command (#1305)
- Updates button styling to sync border widths; updates close button on drawer
- Fixed program info card to render course details link properly

Version 0.56.0 (Released December 20, 2022)
--------------

- Changing the URL so that it ends in /home (rather than /, which directed learners to the about page) (#1295)
- Updates the program drawer to use the requirements tree (#1281)
- fix: program certificate link text (#1282)
- Updates course run and program certificate models to limit choices just to certificate pages in admin

Version 0.55.1 (Released December 19, 2022)
--------------

- fix: certificate template improvements (#1261)
- feat: management command for creating, revoking program certificates (#1260)
- fix: edx-api-client requirement update (#1287)
- Edx verified force enrollment after enrollment end date (#1225)
- Updates program UI to enable unenrollments
- Program drawer remove not enrolled (#1278)
- 1252: dashboard course should not be in progress and ended at the same time (#1279)

Version 0.55.0 (Released December 14, 2022)
--------------

- added program certificates migration from micromasters
- Run command to create initial revisions in `configure_instance` (#1262)
- Removed program readable ID from the card. (#1274)
- 1253: dashboard courses and programs tabs aren't screen reader accessible (#1267)

Version 0.54.6 (Released December 09, 2022)
--------------

- Flipping the default for `for_flexible_pricing` from True to False (#1268)

Version 0.54.5 (Released December 09, 2022)
--------------

- Adds courserun importing from edX (like sync_courserun, but moreso) (#1256)
- Fixes the URL in the partner school email (#1248)

Version 0.54.4 (Released December 08, 2022)
--------------

- fix: program certificate creation should use ProgramRequirement tree (#1239)
- Updates program drawer to handle empty requirements trees, adds function to check for invalid trees

Version 0.54.3 (Released December 07, 2022)
--------------

- Adds "reference_number" to the searchable fields in the BaseOrderAdmin and FulfilledOrderAdmin classes

Version 0.54.2 (Released December 05, 2022)
--------------

- Adds program record functionality
- Change ubuntu-latest to ubuntu-20.04 on all hithub actions yml files

Version 0.54.1 (Released November 22, 2022)
--------------

- 1207 accessibility more dates popup on course pages lacks keyboard controls (#1230)

Version 0.54.0 (Released November 21, 2022)
--------------

- fixing list formatting in generate_discount_code.rst
- Adds some checks to ensure there is a requirements tree before walking it
- Adds some additional options and docs for some management commands

Version 0.53.3 (Released November 17, 2022)
--------------

- 1206 dashboard course detail and view certificate links are too close together (#1209)

Version 0.53.2 (Released November 16, 2022)
--------------

- Adds some code to walk the requirements tree if there are nested operators
- removes ol-django openedx from test_requirements, updates other requirements to get google-sheets-refunds 0.7.0
- Re-groups enrollments in the program drawer and adds tags back to enrollments

Version 0.53.1 (Released November 15, 2022)
--------------

- Fix accidental deletion of requirements

Version 0.53.0 (Released November 14, 2022)
--------------

- added migration to import program enrollments from MicroMaster

Version 0.52.0 (Released November 14, 2022)
--------------

- Fix issues with requirements admin assets

Version 0.51.3 (Released November 04, 2022)
--------------

- Enhance Product admin search and List display (#1194)

Version 0.51.2 (Released November 03, 2022)
--------------

- Add honor code link to account creation dialog (#1187)

Version 0.51.1 (Released November 02, 2022)
--------------

- added a import script to backfill PaidCourseRun for the legacy orders
- Adds wrapper command to bootstrap a fresh MITxOnline instance

Version 0.51.0 (Released November 01, 2022)
--------------

- Add missing import
- Added program requirements data model and admin

Version 0.50.3 (Released October 27, 2022)
--------------

- Adds management command to create a really basic courseware about page.
- Adds a management command to create courseware objects

Version 0.50.2 (Released October 26, 2022)
--------------

- Fix fmt and fmt:check commands
- Adds a management command to create and optionally enroll a user

Version 0.50.1 (Released October 25, 2022)
--------------

- feat: program certificates (#1072)
- feat: User verified course enrollment (#1129)

Version 0.50.0 (Released October 25, 2022)
--------------

- Updating version of mitol-django-payment-gateway to 1.7.1.
- feat: sync is_self_paced from edX (#1158)
- Some changes to the Varnish config; the host was getting set wrong so there were some issues with generated URLs
- Adding simple Varnish config file and service block; should be caching now on port 8013

Version 0.49.4 (Released October 20, 2022)
--------------

- add course certificate migration from MM

Version 0.49.3 (Released October 20, 2022)
--------------

- Adds updated dashboard UI for programs
- Changes staff dashboard to use Django sessions rather than OAuth2

Version 0.49.2 (Released October 19, 2022)
--------------

- 1148: course-enrollment-upgrading-is-not-ever-synchronized-with-edx-if-the-original-update-request-fails (#1151)

Version 0.49.1 (Released October 19, 2022)
--------------

- docs: add information about certificates management (#1136)
- 1143&1144 Fix search and improve loading for e-commerce admin (#1145)

Version 0.49.0 (Released October 17, 2022)
--------------

- Adds a management command to create discount code(s) from the command line
- 1141 Display end date when course ends on dashboard (#1146)
- update course run as raw field on CourseRunGrade admin

Version 0.48.3 (Released October 17, 2022)
--------------

- 1114 Add /checkout/ to no cache urls (#1132)
- Removes unused ecommerce feature flags

Version 0.48.2 (Released October 12, 2022)
--------------

- Updates `configure_for_dedp` command to make it more generic
- Added reference number to list display (#1128)

Version 0.48.1 (Released October 11, 2022)
--------------

- DRYed up the redirect code

Version 0.48.0 (Released October 11, 2022)
--------------

- 1119 Fix basket search for Django admin (#1120)
- Adds additional error reporting; accepts transactions with status code 100
- 1102 Use raw id field for discount in admin (#1112)
- 1115 Use raw id field for order in transactions admin (#1118)
- Fix course model course number property (#1103)
- Updating the enrollment code query to match on email or username now
- 842: sync coursrun upgrade deadline with edx (#1098)
- Added /courses/ to the cache-control list (there's dynamic stuff on course pages; this should keep it out of the Fastly cache)

Version 0.47.3 (Released October 07, 2022)
--------------

- 1094: log information when an order callback request results in an unknown error (#1099)
- Online-1100 Disable price on course page (#1101)
- Save users with no enrollment into file (#1096)
- Updates the call to subscribe to edX emails to be in a post-commit hook

Version 0.47.2 (Released October 04, 2022)
--------------

- made order admin page view-only

Version 0.47.1 (Released October 04, 2022)
--------------

- fixed letter_grade and grade in MM migration query to match with production

Version 0.47.0 (Released October 04, 2022)
--------------

- Fix a small bug in upgrade_eligible_users (#1081)
- Adds dupe checking for generated codes; adds --expires flag to set the expiration date on generated codes
- 1044: when referring to a course in email dont include the full course (#1076)
- fix: show zero for negative prices (#1079)
- update local only enrollments error to filter out unenrolled

Version 0.46.3 (Released October 03, 2022)
--------------

- Upgrade legacy learners that paid and are enrolled, have exam attempt (#1059)
- Revert "1044: when referring to a course in email don't include the full course (#1060)" (#1071)
- 1044: when referring to a course in email don't include the full course (#1060)
- remove unused variables + update eslint config
- Adds management command to generate enrollment codes for legacy learners
- add webpack-bundle-analyzer
- Changes the receipt email subject

Version 0.46.2 (Released September 29, 2022)
--------------

- Online-1035 Display upgrade dialog when Ecommerce enabled (#1065)

Version 0.46.1 (Released September 28, 2022)
--------------

- 1051: Don't display "active" on the dashboard when it is past the course run's course_end date (#1057)
- added management command to create products for DEDP
- 1036 enrolled button on about page links to course before it has started (#1056)
- updated payment response reason code to log error for 1xx
- Bump jwcrypto from 1.0 to 1.4 (#1022)
- Online-1048 Add top margin for footer (#1052)
- Removed an "import this" and updated settings to make cssutils log less verbosely

Version 0.46.0 (Released September 27, 2022)
--------------

- Updates the order fulfillment code to wait for the transaction to complete before sending message
- Missed a spot where get_order_from_cybersource_payment_response needed to be wrapped in a transaction
- Bump oauthlib from 3.1.1 to 3.2.1 (#1008)

Version 0.45.7 (Released September 23, 2022)
--------------

- Fixes duplicate key error when returning to cart using back button

Version 0.45.6 (Released September 22, 2022)
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
