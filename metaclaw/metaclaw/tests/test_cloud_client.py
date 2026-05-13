import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from common.cloud_client import CloudClient


class FakeResponse:
    def __init__(self, status_code=200, content=b"ok", headers=None):
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8", errors="replace")
        self.headers = headers or {}

    def json(self):
        return json.loads(self.text)


@pytest.fixture
def client():
    return CloudClient("http://127.0.0.1:19999", "test-device-123")


def test_request_includes_device_header(client, monkeypatch):
    captured = {}

    def mock_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})
        return FakeResponse()

    import requests as real_requests
    monkeypatch.setattr(real_requests, "request", mock_request)

    client.request("GET", "/api/version")
    assert captured["headers"]["X-Device-Code"] == "test-device-123"
    assert captured["url"] == "http://127.0.0.1:19999/api/version"


def test_request_forwards_body(client, monkeypatch):
    captured = {}

    def mock_request(method, url, **kwargs):
        captured["data"] = kwargs.get("data")
        captured["content_type"] = kwargs.get("headers", {}).get("Content-Type", "")
        return FakeResponse(content=json.dumps({"status": "ok"}).encode())

    import requests as real_requests
    monkeypatch.setattr(real_requests, "request", mock_request)

    body = b'{"message": "hello"}'
    resp = client.request("POST", "/message", {"Content-Type": "application/json"}, body)
    assert captured["data"] == body
    assert captured["content_type"] == "application/json"


def test_request_returns_response_on_success(client, monkeypatch):
    def mock_request(method, url, **kwargs):
        return FakeResponse(status_code=200, content=b'{"version": "1.0"}')

    import requests as real_requests
    monkeypatch.setattr(real_requests, "request", mock_request)

    resp = client.request("GET", "/api/version")
    assert resp.status_code == 200


def test_request_raises_on_connection_error(client, monkeypatch):
    def mock_request(method, url, **kwargs):
        raise Exception("Connection refused")

    import requests as real_requests
    monkeypatch.setattr(real_requests, "request", mock_request)

    with pytest.raises(Exception, match="Connection refused"):
        client.request("GET", "/api/version")


def test_stream_returns_iterator(client, monkeypatch):
    def mock_request(method, url, **kwargs):
        class FakeResp:
            def iter_content(self, chunk_size):
                return iter([b"data: hello\n\n", b"data: world\n\n"])
            def raise_for_status(self):
                pass
        return FakeResp()

    import requests as real_requests
    monkeypatch.setattr(real_requests, "request", mock_request)

    chunks = list(client.stream("GET", "/stream", {}, b""))
    assert chunks == [b"data: hello\n\n", b"data: world\n\n"]
