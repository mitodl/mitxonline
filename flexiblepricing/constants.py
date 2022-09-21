class FlexiblePriceStatus:
    """Statuses for the FlexiblePrice model"""

    APPROVED = "approved"
    AUTO_APPROVED = "auto-approved"
    CREATED = "created"
    PENDING_MANUAL_APPROVAL = "pending-manual-approval"
    DENIED = "denied"
    RESET = "reset"

    ALL_STATUSES = [
        APPROVED,
        AUTO_APPROVED,
        CREATED,
        PENDING_MANUAL_APPROVAL,
        DENIED,
        RESET,
    ]
    TERMINAL_STATUSES = [APPROVED, AUTO_APPROVED, DENIED]

    STATUS_MESSAGES_DICT = {
        APPROVED: "Approved",
        AUTO_APPROVED: "Auto-Approved",
        CREATED: "--",
        PENDING_MANUAL_APPROVAL: "Pending Approval (Documents Received)",
        DENIED: "Denied",
    }


COUNTRY = "country"
DEFAULT_INCOME_THRESHOLD = 75000
INCOME = "income"
INCOME_THRESHOLD_FIELDS = [COUNTRY, INCOME]

FLEXIBLE_PRICE_EMAIL_RESET_SUBJECT = (
    "Update to your personalized course price for {program_name} MITxOnline"
)
FLEXIBLE_PRICE_EMAIL_RESET_MESSAGE = (
    "As requested, we have reset your personalized course price. Please visit "
    "the MITxOnline dashboard and re-submit your annual income information."
)

FLEXIBLE_PRICE_EMAIL_APPROVAL_SUBJECT = (
    "Your personalized course price for {program_name} MITxOnline"
)
FLEXIBLE_PRICE_EMAIL_APPROVAL_MESSAGE = (
    "After reviewing your income documentation, the {program_name} team has awarded you financial "
    "assistance in the amount of {price}.\n\n"
    "You can pay for MITxOnline courses through the MITxOnline portal "
    "(https://MITxOnline.mit.edu/dashboard). All coursework will be conducted on mitxonline.mit.edu"
)

FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_SUBJECT = (
    "Documents received for {program_name} MITxOnline"
)
FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_MESSAGE = (
    "We have received your documents verifying your income. We will review and process them within "
    "5 working days. If you have not received a confirmation email within one week, please feel free "
    "to reply to this email. Otherwise you should receive a confirmation email with your course price. "
    "\n\n"
    "While you are waiting, we encourage you to enroll now and pay later, when a decision has been "
    "reached."
)

INTRO_TEXT = """The cost of courses in the Data, Economics, and Development Policy MicroMasters Program varies between $250 and $1000, depending on your income and ability to pay.<br />
<br />
To see the relationship between income and price, read <a href="https://mitxonline.zendesk.com/hc/en-us/articles/4409893720347-How-much-do-the-DEDP-courses-cost-">How much do the DEDP courses cost?</a>
"""
GUEST_TEXT = """The cost of courses in the Data, Economics, and Development Policy MicroMasters Program varies between $250 and $1000, depending on your income and ability to pay.<br />
<br />
Please create an account or sign in to continue.
"""
APPLICATION_PROCESSING_TEXT = """<h1 data-block-key="pqgxh">Before you can get financial assistance, you need to verify your income.</h1><p data-block-key="68ecf">Please visit the <a href="https://na2.docusign.net/Member/PowerFormSigning.aspx?PowerFormId=4a74536d-1629-4709-b8e9-f173a51cf501&amp;env=na2&amp;v=2">secure DocuSign website</a> to upload an English-translated and notarized income tax or income statement document. You can also send documents by mail. DO NOT SEND BY EMAIL.<br/></p><p data-block-key="c3o1u"><a href="https://mitxonline.zendesk.com/hc/en-us/sections/4409903319323-About-Personalized-Pricing">Frequently Asked Questions</a></p><p data-block-key="4ghi4"></p><p data-block-key="eku23">Upload your documents to DocuSign<br/><a href="https://na2.docusign.net/Member/PowerFormSigning.aspx?PowerFormId=4a74536d-1629-4709-b8e9-f173a51cf501&amp;env=na2&amp;v=2">https://na2.docusign.net/Member/ PowerFormSigning.aspx?PowerFormId=4a74536d-1629-4709-b8e9-f173a51cf501&amp;env=na2&amp;v=2</a></p><p data-block-key="d9eef"></p><p data-block-key="am70h">Or, send Mail to</p><p data-block-key="5d62o">J-PAL<br/> DEDP MicroMasters<br/> Massachusetts Institute of Technology<br/> 77 Massachusetts Avenue E19-235D<br/> Cambridge, MA 02139 United States of America</p>"""
APPLICATION_APPROVED_TEXT = """<h1 data-block-key="txodt">Your Financial Assistance Request is approved!</h1><p data-block-key="91fae">You can now purchase courses in the Data, Economics, and Development Policy program at a reduced rate.</p>"""
APPLICATION_APPROVED_NO_DISCOUNT_TEXT = """<p data-block-key="1423f">You did not qualify for financial assistance.</p><p data-block-key="n07r"></p><p data-block-key="74jdb">You can audit courses for free, or pay full price for a certificate now.</p><p data-block-key="3003a"></p><p data-block-key="6g3dp"><i>If you have questions, contact us using the Help button at the bottom of the page, or e-mail micromasters-support@mit.edu. Due to a high volume of inquiries we do not have a support phone number at this time.</i></p>"""
APPLICATION_DENIED_TEXT = """<p data-block-key="0tusf">Your request for financial assistance has been denied.</p><p data-block-key="clg49"></p><p data-block-key="f0inq">You can audit courses for free, or pay full price for a certificate now.</p><p data-block-key="8l2hb"></p><p data-block-key="pt0p"><i>If you have questions, contact us using the Help button at the bottom of the page, or e-mail micromasters-support@mit.edu. Due to a high volume of inquiries we do not have a support phone number at this time.</i></p>"""

FINAID_FORM_TEXTS = {
    "intro": INTRO_TEXT,
    "guest": GUEST_TEXT,
    "processing": APPLICATION_PROCESSING_TEXT,
    "approved": APPLICATION_APPROVED_TEXT,
    "approved_no_discount": APPLICATION_APPROVED_NO_DISCOUNT_TEXT,
    "denied": APPLICATION_DENIED_TEXT,
}
