"""Courseware exceptions"""
from mitol.common.utils import get_error_response_summary


class OpenEdxUserCreateError(Exception):
    """Exception creating the OpenEdxUser"""


class OpenEdXOAuth2Error(Exception):
    """We were unable to obtain a refresh token from openedx"""


class NoEdxApiAuthError(Exception):
    """The user was expected to have an OpenEdxApiAuth object but does not"""


class EdxApiEnrollErrorException(Exception):
    """An edX enrollment API call resulted in an error response"""

    def __init__(self, user, course_run, http_error, msg=None):
        """
        Sets exception properties and adds a default message

        Args:
            user (users.models.User): The user for which the enrollment failed
            course_run (courses.models.CourseRun): The course run for which the enrollment failed
            http_error (requests.exceptions.HTTPError): The exception from the API call which contains
                request and response data.
        """
        self.user = user
        self.course_run = course_run
        self.http_error = http_error
        if msg is None:
            # Set some default useful error message
            msg = "EdX API error enrolling user {} ({}) in course run '{}'.\n{}".format(
                self.user.username,
                self.user.email,
                self.course_run.courseware_id,
                get_error_response_summary(self.http_error.response),
            )
        super().__init__(msg)


class UnknownEdxApiEnrollException(Exception):
    """An edX enrollment API call failed for an unknown reason"""

    def __init__(self, user, course_run, base_exc, msg=None):
        """
        Sets exception properties and adds a default message

        Args:
            user (users.models.User): The user for which the enrollment failed
            course_run (courses.models.CourseRun): The course run for which the enrollment failed
            base_exc (Exception): The unexpected exception
        """
        self.user = user
        self.course_run = course_run
        self.base_exc = base_exc
        if msg is None:
            msg = "Unexpected error enrolling user {} ({}) in course run '{}' ({}: {})".format(
                self.user.username,
                self.user.email,
                self.course_run.courseware_id,
                type(base_exc).__name__,
                str(base_exc),
            )
        super().__init__(msg)


class UserNameUpdateFailedException(Exception):
    """Raised if a user's profile name(Full Name) update call is failed"""


class EdxApiEmailSettingsErrorException(Exception):
    """An edX change email settings API call resulted in an error response"""

    def __init__(self, user, course_run, http_error, msg=None):
        """
        Sets exception properties and adds a default message

        Args:
            user (users.models.User): The user for which the changes failed
            course_run (courses.models.CourseRun): The course run for which the changes failed
            http_error (requests.exceptions.HTTPError): The exception from the API call which contains
                request and response data.

        """
        self.user = user
        self.course_run = course_run
        self.http_error = http_error
        if msg is None:
            msg = "EdX API error for user {} ({}) course email subscription in course run '{}'.\n{}".format(
                self.user.username,
                self.user.email,
                self.course_run.courseware_id,
                get_error_response_summary(self.http_error.response),
            )
        super().__init__(msg)


class UnknownEdxApiEmailSettingsException(Exception):
    """An edX course email subscription API call failed for an unknown reason"""

    def __init__(self, user, course_run, base_exc, msg=None):
        """
        Sets exception properties and adds a default message

        Args:
            user (users.models.User): The user for which the changes failed
            course_run (courses.models.CourseRun): The course run for which the changes failed
            base_exc (Exception): The unexpected exception
        """
        self.user = user
        self.course_run = course_run
        self.base_exc = base_exc
        if msg is None:
            msg = "Unexpected error for user {} ({}) email subscription in course run '{}' ({}: {})".format(
                self.user.username,
                self.user.email,
                self.course_run.courseware_id,
                type(base_exc).__name__,
                str(base_exc),
            )
        super().__init__(msg)


class EdxApiRegistrationValidationException(Exception):
    """An edX Registration Validation API call resulted in an error response"""

    def __init__(self, username, response, msg=None):
        """
        Sets exception properties and adds a default message

        Args:
            username (str): The username being compared for uniqueness
            response (requests.Response): edX response for username validation
        """
        self.username = username
        self.response = response
        if msg is None:
            # Set some default useful error message
            msg = "EdX API error validating registration username {}.\n{}".format(
                self.username,
                get_error_response_summary(self.response),
            )
        super().__init__(msg)
