from __future__ import annotations

import requests as req_lib


class CloudClient:
    def __init__(self, server_url: str, device_code: str):
        self.server_url = server_url.rstrip("/")
        self.device_code = device_code

    def request(self, method: str, path: str, headers: dict = None, body: bytes = b"") -> req_lib.Response:
        url = f"{self.server_url}{path}"
        fwd_headers = dict(headers) if headers else {}
        fwd_headers["X-Device-Code"] = self.device_code
        return req_lib.request(method, url, headers=fwd_headers, data=body, timeout=300)

    def stream(self, method: str, path: str, headers: dict = None, body: bytes = b""):
        url = f"{self.server_url}{path}"
        fwd_headers = dict(headers) if headers else {}
        fwd_headers["X-Device-Code"] = self.device_code
        resp = req_lib.request(method, url, headers=fwd_headers, data=body, stream=True, timeout=600)
        resp.raise_for_status()
        return resp.iter_content(chunk_size=None)
