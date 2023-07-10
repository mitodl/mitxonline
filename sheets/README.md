Google Sheets
---

This is an explanation of integration with Google Sheets libraries for an 
automated processing of change of enrollment requests.

##Refunds
To learn more on how to set it up follow [this doc](https://github.com/mitodl/ol-django/tree/main/src/mitol/google_sheets_refunds#readme).

###Functionality and Usage
In the MITx Online Google Sheet folder there is a sheet called "MITx Online Production - Change of Enrollment Requests". This
sheet contains a tab "Refund Form Responses", it is getting filled by the "Refund Request" form submissions. This form also resides
within the same folder.

When you fill out the "Refund Request" form your request gets output into the "Refund Form Responses", then copied 
and formatted into the "Refunds" tab within the same document.

From there an automated scheduled task makes an api call to retrieve the data from the tab "Refunds". It parses each 
row checks if the row already has errors present and if it happens to be also unmodified, it ignores the row.
If a request that you submitted has error, you can reprocess this request by clearing the error cell.

If you choose not to process this row again or the request has been resolved another way, set the 
Ignore column to TRUE.

When a row is processed:
1) checks if the Order is in a FULFILLED state
2) retrieves the transaction and checks that the payment method is not PayPal
3) makes a request to CyberSource for refund
4) make a request to edx to change enrollment status to 'audit', updates the CourseRunEnrollment instance.

If the procedure has output a cybersource error then manual resolution is required.

##Deferrals

###Functionality and usage
Within the "MITx Online Production - Change of Enrollment Requests" you can find a "Deferral Request" form. There
are two things you can do with this:
1) Downgrade (aka 'unverify') learner's enrollment for a course run.
2) Transfer the 'verified' enrollment from one course to another

For the first procedure, when fill out the "Deferral Request" form leave the "To Course" blank.
This procedure is pretty straight forward, involving only change of enrollment mode.

The second procedure attempts:
1) to enroll the learner in a 'verified' track for the "To Course"
2) to unenroll the learner from the "From Course"

If 
