"""Deliberately failing test for #4227: shows the merge-ref note on a failed job."""


def test_fails_on_purpose():
    assert False, "deliberate failure to show the merge-ref note"  # noqa: B011, PT015
