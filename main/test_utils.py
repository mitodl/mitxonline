"""Testing utils"""

import csv
import json
import logging
import tempfile
import traceback
from collections import Counter
from contextlib import contextmanager
from functools import cache
from pathlib import Path

import jsonschema
import pytest
import yaml
from deepdiff import DeepDiff
from deepdiff.helper import COLORED_VIEW
from django.conf import settings
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
    diff = DeepDiff(
        converted1, converted2, ignore_order=ignore_order, view=COLORED_VIEW
    )

    if diff != {}:
        pytest.fail(f"Values differ:\n\n{diff!s}")


def _openapi_to_jsonschema(node):
    """Rewrite OpenAPI 3.0's `nullable: true` as JSON Schema's null type."""
    if isinstance(node, list):
        return [_openapi_to_jsonschema(item) for item in node]
    if not isinstance(node, dict):
        return node
    node = {key: _openapi_to_jsonschema(value) for key, value in node.items()}
    if node.get("nullable") is True:
        del node["nullable"]
        return {"anyOf": [node, {"type": "null"}]}
    return node


@cache
def _openapi_spec(version):
    """The committed OpenAPI spec for an API version, as JSON Schema."""
    spec_path = Path(settings.BASE_DIR) / "openapi" / "specs" / f"{version}.yaml"
    with spec_path.open() as spec_file:
        return _openapi_to_jsonschema(yaml.safe_load(spec_file))


def assert_matches_openapi_response(response, path, method, *, version="v0"):
    """
    Assert that a response's JSON body is valid against the schema the committed
    OpenAPI spec documents for the operation and the response's status code,
    i.e. a client validating responses against the spec would accept it.

    Args:
        response: the test client response
        path (str): the operation's path as it appears in the spec
        method (str): the HTTP method
        version (str): the API version whose spec to check against
    """
    spec = _openapi_spec(version)
    schema = spec["paths"][path][method.lower()]["responses"][
        str(response.status_code)
    ]["content"]["application/json"]["schema"]
    # Carry the components along so the schema's $refs resolve.
    jsonschema.validate(response.json(), {**schema, "components": spec["components"]})


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
