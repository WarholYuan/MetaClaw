from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest

from agent.tools.amap.amap_nearby_poi import AmapNearbyPoi


@pytest.fixture
def tool():
    return AmapNearbyPoi()


class TestValidation:
    def test_missing_address_and_location(self, tool):
        result = tool.execute({})
        assert result.status == "error"
        assert "地址或经纬度" in result.result

    def test_missing_amap_worker_url(self, tool):
        with patch.dict(os.environ, {}, clear=True):
            with patch("agent.tools.amap.amap_nearby_poi.conf", return_value={}):
                result = tool.execute({"address": "杭州"})
                assert result.status == "error"
                assert "amap_worker_url" in result.result

    def test_missing_amap_worker_secret(self, tool):
        with patch.dict(os.environ, {"AMAP_WORKER_URL": "https://example.com"}, clear=True):
            with patch("agent.tools.amap.amap_nearby_poi.conf", return_value={"amap_worker_url": "https://example.com"}):
                result = tool.execute({"address": "杭州"})
                assert result.status == "error"
                assert "amap_worker_secret" in result.result


class TestHappyPath:
    @patch("agent.tools.amap.amap_nearby_poi.requests.post")
    @patch("agent.tools.amap.amap_nearby_poi.get_device_code", return_value="abcd1234abcd1234abcd1234abcd1234")
    def test_success(self, mock_device, mock_post, tool):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": True,
            "request_id": "test-id",
            "data": {"unique_count": 5, "rows": [], "summary": {}},
        }
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {
            "AMAP_WORKER_URL": "https://worker.example.com",
            "AMAP_WORKER_SECRET": "secret123",
        }):
            result = tool.execute({"address": "杭州未来研创园", "city": "杭州"})

        assert result.status == "success"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer secret123"
        assert call_kwargs.kwargs["headers"]["X-Device-Code"] == "abcd1234abcd1234abcd1234abcd1234"


class TestErrorHandling:
    @patch("agent.tools.amap.amap_nearby_poi.requests.post")
    @patch("agent.tools.amap.amap_nearby_poi.get_device_code", return_value="abcd1234abcd1234abcd1234abcd1234")
    def test_worker_returns_401(self, mock_device, mock_post, tool):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"ok": False, "error": {"code": "UNAUTHORIZED", "message": "bad token"}}
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {
            "AMAP_WORKER_URL": "https://worker.example.com",
            "AMAP_WORKER_SECRET": "wrong",
        }):
            result = tool.execute({"address": "杭州"})

        assert result.status == "error"
        assert "鉴权失败" in result.result

    @patch("agent.tools.amap.amap_nearby_poi.requests.post")
    @patch("agent.tools.amap.amap_nearby_poi.get_device_code", return_value="abcd1234abcd1234abcd1234abcd1234")
    def test_worker_returns_qps_error(self, mock_device, mock_post, tool):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": False,
            "request_id": "test-id",
            "error": {"code": "AMAP_QPS_EXCEEDED", "message": "限流", "retryable": True},
        }
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {
            "AMAP_WORKER_URL": "https://worker.example.com",
            "AMAP_WORKER_SECRET": "secret123",
        }):
            result = tool.execute({"address": "杭州"})

        assert result.status == "error"
        assert "繁忙" in result.result

    @patch("agent.tools.amap.amap_nearby_poi.requests.post")
    @patch("agent.tools.amap.amap_nearby_poi.get_device_code", return_value="abcd1234abcd1234abcd1234abcd1234")
    def test_timeout(self, mock_device, mock_post, tool):
        mock_post.side_effect = __import__("requests").Timeout("timeout")

        with patch.dict(os.environ, {
            "AMAP_WORKER_URL": "https://worker.example.com",
            "AMAP_WORKER_SECRET": "secret123",
        }):
            result = tool.execute({"address": "杭州"})

        assert result.status == "error"
        assert "超时" in result.result
