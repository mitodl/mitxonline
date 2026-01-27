"""Constants for the courses app"""

UAI_COURSEWARE_ID_PREFIX = "course-v1:UAI_"

CONTENT_TYPE_MODEL_PROGRAM = "program"
CONTENT_TYPE_MODEL_COURSE = "course"
CONTENT_TYPE_MODEL_COURSERUN = "courserun"
DEFAULT_COURSE_IMG_PATH = "images/mit-dome.png"
VALID_PRODUCT_TYPES = {CONTENT_TYPE_MODEL_COURSERUN, CONTENT_TYPE_MODEL_PROGRAM}
VALID_PRODUCT_TYPE_CHOICES = list(zip(VALID_PRODUCT_TYPES, VALID_PRODUCT_TYPES))

PROGRAM_TEXT_ID_PREFIX = "program-"
ENROLLABLE_ITEM_ID_SEPARATOR = "+"
TEXT_ID_RUN_TAG_PATTERN = rf"\{ENROLLABLE_ITEM_ID_SEPARATOR}(?P<run_tag>R\d+)$"
PROGRAM_RUN_ID_PATTERN = (
    rf"^(?P<text_id_base>{PROGRAM_TEXT_ID_PREFIX}.*){TEXT_ID_RUN_TAG_PATTERN}"
)

ENROLL_CHANGE_STATUS_DEFERRED = "deferred"
ENROLL_CHANGE_STATUS_TRANSFERRED = "transferred"
ENROLL_CHANGE_STATUS_REFUNDED = "refunded"
ENROLL_CHANGE_STATUS_UNENROLLED = "unenrolled"
ALL_ENROLL_CHANGE_STATUSES = [
    ENROLL_CHANGE_STATUS_DEFERRED,
    ENROLL_CHANGE_STATUS_TRANSFERRED,
    ENROLL_CHANGE_STATUS_REFUNDED,
    ENROLL_CHANGE_STATUS_UNENROLLED,
]
ENROLL_CHANGE_STATUS_CHOICES = list(
    zip(ALL_ENROLL_CHANGE_STATUSES, ALL_ENROLL_CHANGE_STATUSES)
)

SYNCED_COURSE_RUN_FIELD_MSG = "This value is synced automatically with edX studio."

AVAILABILITY_ANYTIME = "anytime"
AVAILABILITY_DATED = "dated"
AVAILABILITY_TYPES = [AVAILABILITY_ANYTIME, AVAILABILITY_DATED]
AVAILABILITY_CHOICES = list(zip(AVAILABILITY_TYPES, AVAILABILITY_TYPES))

COURSE_KEY_PATTERN = r"^course-v1:[^+]+\+[^+]+\+[^+]+$"
# Courseware URL generation pattern
# The courseware URL for a course run follows this pattern:
# <edX base URL>/learn/course/<readable id>/home
#
# This is used to generate the courseware URL for a course run, which is
# computed from the readable_id (courseware_id) and the edX base URL configured
# in settings (OPENEDX_BASE_REDIRECT_URL).
#
# Example: https://edx.example.com/learn/course/course-v1:MITx+18.01x+3T2023/home
#
# Configuration Settings:
# - OPENEDX_BASE_REDIRECT_URL: the base URL for edX redirects (e.g., https://edx.example.com)
#
# The generated URL uses the pattern: {OPENEDX_BASE_REDIRECT_URL}/learn/course/{readable_id}/home
COURSEWARE_URL_PATTERN_TEMPLATE = "/learn/course/{courseware_id}/home"
