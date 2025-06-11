import pytest

from main.env import EnvironmentVariableParseException, get_float

FAKE_ENVIRONS = {
    "true": "True",
    "false": "False",
    "positive": "123",
    "negative": "-456",
    "zero": "0",
    "float-positive": "1.1",
    "float-negative": "-1.1",
    "float-zero": "0.0",
    "expression": "123-456",
    "none": "None",
    "string": "a b c d e f g",
    "list_of_int": "[3,4,5]",
    "list_of_str": '["x", "y", \'z\']',
}


def test_get_float(mocker):
    """
    get_float should get the float from the environment variable, or raise an exception if it's not parseable as an float
    """
    mocker.patch.dict("os.environ", FAKE_ENVIRONS)

    assert get_float("positive", 1234) == 123
    assert get_float("negative", 1234) == -456
    assert get_float("zero", 1234) == 0
    assert get_float("float-positive", 1234) == 1.1
    assert get_float("float-negative", 1234) == -1.1
    assert get_float("float-zero", 1234) == 0.0

    for key, value in FAKE_ENVIRONS.items():
        if key not in (
            "positive",
            "negative",
            "zero",
            "float-zero",
            "float-positive",
            "float-negative",
        ):
            with pytest.raises(
                EnvironmentVariableParseException,
            ) as ex:
                get_float(key, 1234)
            assert ex.value.args[0] == f"Expected value in {key}={value} to be a float"

    assert get_float("missing", "default") == "default"
