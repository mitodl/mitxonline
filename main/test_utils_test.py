"""Tests for test utils"""

import pytest

from main.test_utils import MockResponse, assert_drf_json_equal, assert_not_raises


def test_assert_not_raises_none():
    """
    assert_not_raises should do nothing if no exception is raised
    """
    with assert_not_raises():
        pass


def test_assert_not_raises_exception(mocker):
    """assert_not_raises should fail the test"""
    # Here there be dragons
    fail_mock = mocker.patch("pytest.fail", autospec=True)
    with assert_not_raises():
        raise TabError
    assert fail_mock.called is True


def test_assert_not_raises_failure():
    """assert_not_raises should reraise an AssertionError"""
    with pytest.raises(AssertionError):  # noqa: SIM117
        with assert_not_raises():
            assert 1 == 2  # noqa: PLR0133


def test_assert_drf_json_equall():
    """Asserts that objects are equal in JSON"""
    assert_drf_json_equal({"a": 1}, {"a": 1})
    assert_drf_json_equal(2, 2)
    assert_drf_json_equal([2], [2])


@pytest.mark.parametrize(
    "content,expected_content,expected_json",  # noqa: PT006
    [
        ['{"test": "content"}', '{"test": "content"}', {"test": "content"}],  # noqa: PT007
        [{"test": "content"}, '{"test": "content"}', {"test": "content"}],  # noqa: PT007
        [["test", "content"], '["test", "content"]', ["test", "content"]],  # noqa: PT007
        [123, "123", 123],  # noqa: PT007
    ],
)
def test_mock_response(content, expected_content, expected_json):
    """Assert MockResponse returns correct values"""
    response = MockResponse(content, 404)
    assert response.status_code == 404
    assert response.content == expected_content
    assert response.json() == expected_json
