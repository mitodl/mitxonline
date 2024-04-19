"""
Exceptions for flexible pricing
"""


class CountryIncomeThresholdException(Exception):  # noqa: N818
    """
    Execption regarding import country income csv files
    """


class ExceededAPICallsException(Exception):  # noqa: N818
    """
    Exceeded maximum number of API calls per month to Open Exchange Rates (openexchangerates.org)
    """


class UnexpectedAPIErrorException(Exception):  # noqa: N818
    """
    Unexpected error in making an API call
    """


class NotSupportedException(Exception):  # noqa: N818
    """
    Not supported by current flexible price system.
    """
