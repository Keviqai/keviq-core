"""Unit tests for request ID context management."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mona_os_logger.context import get_request_id, new_request_id, set_request_id


def test_default_request_id_is_empty():
    set_request_id("")
    assert get_request_id() == ""


def test_set_and_get_request_id():
    set_request_id("test-id-123")
    assert get_request_id() == "test-id-123"
    set_request_id("")  # cleanup


def test_new_request_id_is_uuid_format():
    rid = new_request_id()
    parts = rid.split("-")
    assert len(parts) == 5
    assert len(rid) == 36


def test_new_request_id_is_unique():
    ids = {new_request_id() for _ in range(100)}
    assert len(ids) == 100


def test_set_request_id_overwrite():
    set_request_id("first")
    set_request_id("second")
    assert get_request_id() == "second"
    set_request_id("")  # cleanup


def test_set_request_id_empty_string():
    set_request_id("")
    assert get_request_id() == ""
