"""
Exceptions for flexible pricing
"""


class CountryIncomeThresholdException(Exception):
    """
    Execption regarding import country income csv files
    """


class ExceededAPICallsException(Exception):
    """
    Exceeded maximum number of API calls per month to Open Exchange Rates (openexchangerates.org)
    """


class UnexpectedAPIErrorException(Exception):
    """
    Unexpected error in making an API call
    """
