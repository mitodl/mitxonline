// Put constants here

export const ENROLLABLE_ITEM_ID_SEPARATOR = "+"
export const PRODUCT_TYPE_PROGRAM = "program"
export const PRODUCT_TYPE_COURSERUN = "courserun"

export const GENDER_CHOICES = [
  ["m", "Male"],
  ["f", "Female"],
  ["o", "Other/Prefer Not to Say"]
]

export const EMPLOYMENT_INDUSTRY = [
  "Association, Nonprofit Organization, NGO",
  "Business and Professional Services",
  "Construction and Engineering",
  "Education",
  "Energy",
  "Financials",
  "Government / Armed Forces",
  "Food, Beverages and Tobacco",
  "Government",
  "Health Care",
  "Industrials",
  "Retailing",
  "Materials",
  "Media",
  "Information technology",
  "Transportation",
  "Other",
  "Prefer not to say"
]

export const EMPLOYMENT_EXPERIENCE = [
  [2, "Less than 2 years"],
  [5, "2-5 years"],
  [10, "6 - 10 years"],
  [15, "11 - 15 years"],
  [20, "16 - 20 years"],
  [21, "More than 20 years"],
  [0, "Prefer not to say"]
]

export const EMPLOYMENT_SIZE = [
  [1, "Small/Start-up (1+ employees)"],
  [9, "Small/Home office (1-9 employees)"],
  [99, "Small (10-99 employees)"],
  [999, "Small to medium-sized (100-999 employees)"],
  [9999, "Medium-sized (1000-9999 employees)"],
  [10000, "Large Enterprise (10,000+ employees)"],
  [0, "Other (N/A or Don't know)"]
]

export const EMPLOYMENT_FUNCTION = [
  "Accounting",
  "Administrative",
  "Arts and Design",
  "Business Development/Sales",
  "Community & Social Services",
  "Consulting",
  "Education",
  "Engineering",
  "Entrepreneurship",
  "Finance",
  "Healthcare Services",
  "Human Resources",
  "Information Technology",
  "Legal",
  "Media/Communications/Marketing",
  "Military & Protective Services",
  "Operations",
  "Program & Product Management",
  "Purchasing",
  "Quality Assurance",
  "Real Estate",
  "Research",
  "Support",
  "Other"
]

export const EMPLOYMENT_LEVEL = [
  "Upper Management",
  "Middle Management",
  "Junior First Line Management",
  "Individual Contributor",
  "Consultant/Contractor",
  "Temporary Employee",
  "Other",
  "Prefer not to say"
]

export const HIGHEST_EDUCATION_CHOICES = [
  "Doctorate",
  "Master's or professional degree",
  "Bachelor's degree",
  "Associate degree",
  "Secondary/high school",
  "Junior secondary/junior high/middle school",
  "Elementary/primary school",
  "No formal education",
  "Other education"
]

export const USER_MSG_COOKIE_NAME = "user-message"
export const USER_MSG_TYPE_ENROLLED = "enrolled"
export const USER_MSG_TYPE_ENROLL_FAILED = "enroll-failed"
export const USER_MSG_TYPE_ENROLL_BLOCKED = "enroll-blocked"
export const USER_MSG_TYPE_ENROLL_DUPLICATED = "enroll-duplicated"
export const USER_MSG_TYPE_COMPLETED_AUTH = "completed-auth"
export const USER_MSG_TYPE_PROFILE_CREATED = "profile-created"
export const USER_MSG_TYPE_COURSE_NON_UPGRADABLE = "course-non-upgradable"

export const USER_MSG_TYPE_PAYMENT_DECLINED = "payment-declined"
export const USER_MSG_TYPE_PAYMENT_ERROR = "payment-error"
export const USER_MSG_TYPE_PAYMENT_CANCELLED = "payment-cancelled"
export const USER_MSG_TYPE_PAYMENT_REVIEW = "payment-review"
export const USER_MSG_TYPE_PAYMENT_ACCEPTED = "payment-accepted"
export const USER_MSG_TYPE_PAYMENT_ACCEPTED_NO_VALUE =
  "payment-accepted-no-value"
export const USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN = "payment-error-unknown"
export const USER_MSG_TYPE_DISCOUNT_INVALID = "discount-invalid"
export const USER_MSG_TYPE_REQUIRED_ENROLLMENT_CODE_EMPTY = "required-enrollment-code-empty"

export const ALERT_TYPE_TEXT = "text"
export const ALERT_TYPE_SUCCESS = "success"
export const ALERT_TYPE_DANGER = "danger"

// HTML title for different pages
export const DASHBOARD_PAGE_TITLE = "Dashboard"

export const LOGIN_EMAIL_PAGE_TITLE = "Sign In"
export const LOGIN_PASSWORD_PAGE_TITLE = LOGIN_EMAIL_PAGE_TITLE

export const FORGOT_PASSWORD_PAGE_TITLE = "Forgot Password"
export const FORGOT_PASSWORD_CONFIRM_PAGE_TITLE = FORGOT_PASSWORD_PAGE_TITLE

export const EDIT_PROFILE_PAGE_TITLE = "Edit Profile"
export const VIEW_PROFILE_PAGE_TITLE = "Profile Information"

export const REGISTER_EMAIL_PAGE_TITLE = "Register"
export const REGISTER_CONFIRM_PAGE_TITLE = REGISTER_EMAIL_PAGE_TITLE
export const REGISTER_DETAILS_PAGE_TITLE = REGISTER_EMAIL_PAGE_TITLE
export const REGISTER_EXTRA_DETAILS_PAGE_TITLE = REGISTER_EMAIL_PAGE_TITLE

export const REGISTER_ERROR_PAGE_TITLE = "Registration Error"
export const REGISTER_DENIED_PAGE_TITLE = REGISTER_ERROR_PAGE_TITLE

export const ACCOUNT_SETTINGS_PAGE_TITLE = "My Account"
export const EMAIL_CONFIRM_PAGE_TITLE = "Confirm Email Change"

export const CART_DISPLAY_PAGE_TITLE = "Checkout"

export const ORDER_HISTORY_DISPLAY_PAGE_TITLE = "Order History"

export const ORDER_RECEIPT_DISPLAY_PAGE_TITLE = "Order Receipt"

export const ORDER_HISTORY_COLUMN_TITLES = [
  "Items",
  "Date placed",
  "Total cost",
  "Order number",
  "Order details"
]

export const DISCOUNT_TYPE_FIXED_PRICE = "fixed-price"
export const DISCOUNT_TYPE_DOLLARS_OFF = "dollars-off"
export const DISCOUNT_TYPE_PERCENT_OFF = "percent-off"

export const RECORDS_PAGE_TITLE = "Program Record"

/* Program Requirements constants */
export const NODETYPE_ROOT = "program_root"
export const NODETYPE_OPERATOR = "operator"
export const NODETYPE_COURSE = "course"

export const NODEOPER_ALL = "all_of"
export const NODEOPER_MIN = "min_number_of"
