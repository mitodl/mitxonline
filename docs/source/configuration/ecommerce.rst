Configure eCommerce
===================

To use the eCommerce subsystem, some configuration is required. These instructions will also set up a course in your MITxOnline environment that you can use for enrollment.

You'll need a working MITxOnline setup and a working devstack setup to begin, and superuser accounts for each.

Set Up MITxOnline eCommerce Config
##################################

The CyberSource configuration for the app can be lifted out of Heroku. **Make sure you use values from RC - otherwise, you will actually be charged for purchases (and test credit card numbers will fail).** For best results, you should also have an account for the test Enterprise Business Center (``https://ebc2test.cybersource.com/ebc2/``). 

The ``.env`` settings you need to copy over are:

- ``MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY``
- ``MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID``
- ``MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY``
- ``MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL``

Alternatively, you can set up your own CyberSource developer account and generate a set of API keys there: `Evaluation Account Setup <https://ebc2.cybersource.com/ebc2/registration/external>`_ If you set up your own developer account, you will need to properly configure it for Secure Acceptance with the credit card types you wish to test, and you will need to generate your own API keys and supply them in the ``.env`` file.

You may also set ``ECOMMERCE_DEFAULT_PAYMENT_GATEWAY`` to ``CyberSource`` - this sets it to the default value, but setting it now will prevent issues if the Payment Gateway ol-django library adds in new payment gateways.

Set Up a Course
###############

The devstack environment comes with a couple of test courses set up. If you want a different course, you will need to set that up in Open edX before starting here. Bootstrapping a course in edX is beyond the scope of this document.

In Open edX
-----------

1. Log in to the Django Admin interface.
2. Find a course from the `Course Overviews <http://edx.odl.local:18000/admin/course_overviews/courseoverview/>`_ page.
3. Note the *Display name* and *Id* fields. 

In MITxOnline
-------------

1. Log into the Django Admin interface.
2. Under Courses, open Programs and add a Program. (The specifics here aren't important - there just needs to be a Program.)
3. Under Courses, open Courses and add a Course. The *Title* and *Readable Id* fields should be set to the *Display name* and *Id* fields from the edX course you plan to use. Make sure Live is set and the Program is set to the program you created in step 2.
4. Under Course Runs, add a Course Run. The *Title* and *Courseware Id* fields should be set to the Id and Display Name fields from the edX course. The Courseware url path should be set to the URL where the course lives in edX (ex. ``https://courses-qa.mitxonline.mit.edu/learn/course/course-v1:MITx+14.750x+3T2022/home``). The dates will be overwritten when the system is synced with Open edX, but for testing it's good to put Start Date, End Date, Enrollment Start, and Enrollment End. A good starting point for these is today plus/minus one year for each. 
5. You now need to add the course to the CMS. Navigate to the Wagtail CMS admin, at /cms. 
6. Open the Courses folder under Home Page. 
7. Select Add Child Page.
8. Fill out the form. The course you added in steps 1-4 should appear. (If not, double-check your settings in Django Admin.) Publish the page when ready.
9. Open the Home Page, and select Edit. 
10. Under the Featured Products section, select Add. You will be given a button to choose a page, and the page chooser there should list the page you created. 
11. Publish the Home Page when ready. 

You should now be able to see the course under the hero image on the MITxOnline homepage, and navigating into the course should give you the option to Enroll. (At this point, you won't have a Product set up, so enrolling now should just enroll you in the course.)

Setting Up a Product
####################

1. Log into MITxOnline Django Admin.
2. Under Ecommerce, open Products and create a new Product. Set *Content type* to Course Run and *Object Id* to the ID of the course run you created earlier (it's probably 1 if you're working from a new install). Price should ideally be set to a non-zero value, that is less than $999, in RC/Sandbox environments. Description needs to be filled in but can be anything - for clarity, it's recommended to use the course name. Make sure Is active is checked.

You should now be able to enroll in the upgraded course. 

* If you've enrolled in the course already, you should now see the upsell card on the course listing page. 
* If you haven't enrolled, enrolling should pop the upgrade modal. 
* In either case, enrolling in the paid version of the course should bring you to the cart, and you should then be able to check out. 

Testing Checkout
----------------

The test CyberSource credentials won't actually process a charge that has been run through the system. However, you should avoid using a valid credit card number when testing. Any card number that is both invalid but passes the checks should work. Here are some examples:

- Visa: 4111111111111111
- Visa: 4242424242424242
- MasterCard: 5555555555554444
- MasterCard: 5105105105105100
- American Express: 378282246310005
- Discover: 6011111111111117

Supply any expiration date in the future. The CVN code should be any three-digit (not AmEx) or 4 digit (AmEx) number that is fairly unique (not like 123, 111). What card types are allowed and whether or not the CVN code is required depends on the settings in the CyberSource account - currently, the MIT test account does require an expiration date and CVN code and supports the four card types listed above. Transactions are logged and can be found in the test EBC. You can additionally adjust the settings in the EBC to email the payment data to you while you're testing - but you should ask around before doing this in case someone else is testing eCommerce elsewhere. 

