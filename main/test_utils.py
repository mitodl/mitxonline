"""Testing utils"""

import csv
import json
import logging
import tempfile
import traceback
from collections import Counter
from contextlib import contextmanager

import pytest
from deepdiff import DeepDiff
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from requests.exceptions import HTTPError
from rest_framework.renderers import JSONRenderer


@contextmanager
def assert_not_raises():
    """Used to assert that the context does not raise an exception"""
    try:
        yield
    except AssertionError:
        raise
    except Exception:  # pylint: disable=broad-except  # noqa: BLE001
        pytest.fail(f"An exception was not raised: {traceback.format_exc()}")


def assert_drf_json_equal(obj1, obj2, ignore_order=False):  # noqa: FBT002
    """
    Asserts that two objects are equal after a round trip through JSON serialization/deserialization.
    Particularly helpful when testing DRF serializers where you may get back OrderedDict and other such objects.

    Args:
        obj1 (object): the first object
        obj2 (object): the second object
        ignore_order (bool): Boolean to ignore the order in the result
    """
    json_renderer = JSONRenderer()
    converted1 = json.loads(json_renderer.render(obj1))
    converted2 = json.loads(json_renderer.render(obj2))
    if ignore_order:
        assert DeepDiff(converted1, converted2, ignore_order=ignore_order) == {}
    else:
        assert converted1 == converted2


class MockResponse:
    """
    Mock requests.Response
    """

    def __init__(
        self, content, status_code=200, content_type="application/json", url=None
    ):
        if isinstance(content, dict | list):
            self.content = json.dumps(content)
        else:
            self.content = str(content)
        self.text = self.content
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        if url:
            self.url = url

    def json(self):
        """Return json content"""
        return json.loads(self.content)


class MockHttpError(HTTPError):
    """Mocked requests.exceptions.HttpError"""

    def __init__(self, *args, **kwargs):
        response = MockResponse(content={"bad": "response"}, status_code=400)
        super().__init__(*args, **{**kwargs, "response": response})


def drf_datetime(dt):
    """
    Returns a datetime formatted as a DRF DateTimeField formats it

    Args:
        dt(datetime): datetime to format

    Returns:
        str: ISO 8601 formatted datetime
    """
    return dt.isoformat().replace("+00:00", "Z")


def create_tempfile_csv(rows_iter):
    """
    Creates a temporary CSV file for use in testing file upload views

    Args:
        rows_iter (iterable of lists): An iterable of lists of strings representing the csv values.
            Example: [["a","b","c"], ["d","e","f"]] --> CSV contents: "a,b,c\nd,e,f"

    Returns:
        SimpleUploadedFile: A temporary CSV file with the given contents
    """
    f = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)  # noqa: SIM115
    with open(f.name, "w", encoding="utf8", newline="") as f:  # noqa: PTH123
        writer = csv.writer(f, delimiter=",")
        for row in rows_iter:
            writer.writerow(row)
    with open(f.name) as user_csv:  # noqa: PTH123
        return SimpleUploadedFile(
            f.name, user_csv.read().encode("utf8"), content_type="application/csv"
        )


def format_as_iso8601(time):
    """Helper function to format datetime with the Z at the end"""
    # Can't use datetime.isoformat() because format is slightly different from this
    iso_format = "%Y-%m-%dT%H:%M:%S"
    formatted_time = time.strftime(iso_format)
    if time.microsecond:
        miniseconds_format = ".%f"
        formatted_time += time.strftime(miniseconds_format)[:4]
    return formatted_time + "Z"


def list_of_dicts(specialty_dict_iter):
    """
    Some library methods yield an OrderedDict or defaultdict, and it's easier to confirm their contents using a
    regular dict. This function turns an iterable of specialty dicts into a list of normal dicts.

    Args:
        specialty_dict_iter:

    Returns:
        list of dict: A list of dicts
    """
    return list(map(dict, specialty_dict_iter))


def set_request_session(mocker, request, session_dict):
    """
    Sets session variables on a RequestFactory object
    Args:
        request (WSGIRequest): A RequestFactory-produced request object (from RequestFactory.get(), et. al.)
        session_dict (dict): Key/value pairs of session variables to set

    Returns:
        RequestFactory: The same request object with session variables set
    """
    get_response = mocker.MagicMock()
    middleware = SessionMiddleware(get_response)
    middleware.process_request(request)
    for key, value in session_dict.items():
        request.session[key] = value
    request.session.save()
    return request


def update_namespace(tuple_to_update, **updates):
    """
    Returns a new namespace with the same properties as the input, but updated with
    the given kwargs.

    Args:
        tuple_to_update (Union([types.namedtuple, typing.NamedTuple])): The tuple object
        **updates: Properties to update on the tuple

    Returns:
        Union([types.namedtuple, typing.NamedTuple]): The updated namespace
    """
    return tuple_to_update.__class__(
        **{  # pylint: disable=protected-access
            **tuple_to_update._asdict(),  # pylint: disable=protected-access
            **updates,
        }
    )


def duplicate_queries_check(context):
    """
    For now this is informational until we fix the queries, then we will swap this over
    to an assertion that captured_queries_list == list(set(captured_queries_list))
    """
    captured_queries_list = [
        query_dict["sql"] for query_dict in context.captured_queries
    ]
    total_queries = len(captured_queries_list)
    count_of_requests = Counter(captured_queries_list)
    if max(count_of_requests.values()) > 1:
        logger = logging.getLogger()
        dupes = [value for query, value in count_of_requests.items() if value > 1]
        logger.info(
            f"{len(dupes)} out of {total_queries} queries duplicated",  # noqa: G004
            stacklevel=2,
        )
