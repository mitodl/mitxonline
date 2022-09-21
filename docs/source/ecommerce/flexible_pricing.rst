Flexible Pricing
================

The Flexible Pricing system allows learners to request alternative pricing for MITxOnline courses based on their location and annual income. These requests can be made through a customizable form in the Wagtail CMS system.

When the learner accesses the Flexible Pricing request form, they will see one of the following:

* If they aren't logged in, they'll see a message saying so. Learners must be logged in to request flexibile pricing.
* If they haven't submitted a request, they'll see the flexible pricing form and will be able to submit a request. On submission, the learner will see a message saying their request has been approved (if it can be approved automatically), or will see a request for more information to be submitted via DocuSign.  
* If they have submitted a request, they'll be presented with a status page for their request. The text for approved, denied, and in progress states can be customized. 

Form Creation
*************

*To manually create a Flexible Pricing request form,* follow these steps:

1. Navigate to the course page for the course. (Do not click the pencil button to edit, simply select the page itself.)
2. Click the Add Child Page button in the header.
3. You will be presented with the New Flexible Pricing Request Form page. Fill out the form.
 
   1. The Intro field text is displayed on the form regardless of the state of the request. 
   2. The Guest text is displayed if the learner isn't logged in yet.
   3. The Application Processing text is displayed if the learner navigates to the form again and their application is still being processed.
   4. The Application Approved text is displayed if the learner navigates to the form and their application has been approved.
   5. The Application Approved No Discount text is displayed if the learner navigates to the form and their application has been approved, but they've been approved for a zero-value tier. (In other words, the learner has exceeded the upper limit of flexible pricing.)
   6. The Application Denied text is displayed if the learner navigates to the form and their application has been denied.
   7. The Form Fields are the data that the learner must provide to be considered for flexible pricing. Leave this alone - the system will automatically add the proper fields when the form is published.
  
4. Publish the form when you are ready. 
5. Navigate back to the course page for the course, and edit the page. Add a link to the flexible pricing form you created in the page content. 
6. Publish the course page when you are ready. 

To add the Flexible Pricing form to the Price card on a course page, first get the link to the live form. This can be done on the edit page for the flexible pricing form (as well as in a few other locations within the CMS). Then, add that link to the Link field in the Price card for the course. 

*To generate a Flexible Pricing request form with some reasonable defaults for your courseware object,* use the ``create_finaid_form`` management command:

.. code-block:: bash

   $ manage.py create_finaid_form [--force] [--slug <slug name here>] [--title <title here>] courseware-readable-id

This command will create an appropriate flexible pricing form for the courseware object:

* If you've specified a Program, the form will be located under the program's page in the CMS.
* If you've specified a standalone Course, the form will be located under the course's page in the CMS.
* If you've specified a Course that is in a Program, the form will be located under the program's page in the CMS, *unless* the ``--force`` option is specified. In that case, the form will be under the course page.

You can customize the title and slug using their respective options. By default, the system will use the object's title to generate a form title and slug. 

Processing Submitted Request
****************************

TBD