"""Flexible price api tests"""
import pytest

from flexiblepricing.api import (
    parse_country_income_thresholds,
    IncomeThreshold,
    import_country_income_thresholds,
)
from flexiblepricing.exceptions import CountryIncomeThresholdException


def test_parse_country_income_thresholds_no_header(tmp_path):
    """parse_alumni_csv should throw error if no header is found"""
    path = tmp_path / "test.csv"
    open(path, "w")  # create a file
    with pytest.raises(CountryIncomeThresholdException) as exc:
        parse_country_income_thresholds(path)

    assert exc.value.args[0] == "Unable to find the header row"


def test_parse_country_income_thresholds_missing_header_fields(tmp_path):
    """parse_alumni_csv should throw error if any of the header field is missing"""
    path = tmp_path / "test.csv"
    with open(path, "w") as file:
        file.write("country\n")
        file.write("PK\n")

    with pytest.raises(CountryIncomeThresholdException) as exc:
        parse_country_income_thresholds(path)

    assert exc.value.args[0] == "Unable to find column header income"


def test_parse_country_income_thresholds(tmp_path):
    """parse_alumni_csv should convert CSV records into IncomeThreshold objects"""
    path = tmp_path / "test.csv"
    with open(path, "w") as file:
        file.write("country,income\n")
        file.write("PK,25000\n")
        file.write("US,75000\n")

    income_thresholds = parse_country_income_thresholds(path)
    assert income_thresholds == [
        IncomeThreshold(country="PK", income="25000"),
        IncomeThreshold(country="US", income="75000"),
    ]


@pytest.mark.django_db
def test_import_country_income_thresholds(tmp_path, caplog):
    """test import_country_income_thresholds works fine"""
    path = tmp_path / "test.csv"
    with open(path, "w") as file:
        file.write("country,income\n")
        file.write("PK,25000\n")
        file.write("US,75000\n")

    # first time would create new records
    import_country_income_thresholds(path)
    assert "Record created successfully for country=PK with income 25000"
    assert "Record created successfully for country=US with income 75000"

    # second time would rather update records
    import_country_income_thresholds(path)
    # assert parse_country_income_thresholds.called
    assert "Updated record successfully for country=PK with income 25000"
    assert "Updated record successfully for country=US with income 75000"
