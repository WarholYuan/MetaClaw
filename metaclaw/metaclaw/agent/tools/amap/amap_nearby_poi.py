from __future__ import annotations

import os
from typing import Any, Dict

import requests

from agent.tools.base_tool import BaseTool, ToolResult
from common.device import get_device_code
from common.log import logger
from config import conf

DEFAULT_TIMEOUT = 30

ERROR_TRANSLATIONS = {
    "UNAUTHORIZED": "amap worker 鉴权失败，请联系管理员检查配置",
    "BAD_REQUEST": "请求参数错误",
    "GEOCODE_NO_RESULT": "找不到这个地点，请提供更具体的地址或直接给经纬度",
    "AMAP_QPS_EXCEEDED": "高德接口繁忙，请稍后再问",
    "AMAP_QUOTA_EXCEEDED": "高德今日额度已用尽，请明日再试或联系管理员",
    "AMAP_KEY_INVALID": "amap worker 内部 key 异常，请联系管理员",
    "AMAP_OTHER_ERROR": "高德返回错误",
    "UPSTREAM_TIMEOUT": "高德接口超时，请稍后再问",
    "INTERNAL_ERROR": "amap worker 内部错误",
}


class AmapNearbyPoi(BaseTool):
    name: str = "amap_nearby_poi"
    description: str = (
        "Query nearby points of interest (shops, restaurants, businesses) "
        "around an address or coordinate using AMap. "
        "Use when the user asks about nearby merchants, places, or services. "
        "Provide either 'address' (e.g., '杭州未来研创园') or 'location' "
        "('lng,lat'). Returns list of POIs with name, distance, address, "
        "rating, phone, opening hours."
    )
    params: dict = {
        "type": "object",
        "properties": {
            "address": {"type": "string", "description": "地名或地址，如 '杭州未来研创园'"},
            "location": {"type": "string", "description": "经纬度，格式 'lng,lat'"},
            "city": {"type": "string", "description": "城市名，辅助 geocode 定位"},
            "radius": {"type": "integer", "description": "搜索半径（米），1-50000，默认 3000"},
            "keywords": {"type": "string", "description": "关键词筛选，如 '餐饮'、'咖啡'"},
            "types": {"type": "string", "description": "POI 类型代码，如 '050000'"},
            "target_count": {"type": "integer", "description": "期望返回数量，1-1000，默认 200"},
        },
        "required": [],
    }

    @staticmethod
    def is_available() -> bool:
        return bool(
            os.environ.get("AMAP_WORKER_URL")
            or conf().get("amap_worker_url", "")
        )

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        address = (args.get("address") or "").strip()
        location = (args.get("location") or "").strip()

        if not address and not location:
            return ToolResult.fail("地址或经纬度至少要给一个")

        worker_url = os.environ.get("AMAP_WORKER_URL") or conf().get("amap_worker_url", "")
        if not worker_url:
            return ToolResult.fail("amap_worker_url 未配置，无法使用高德周边搜索")

        worker_secret = os.environ.get("AMAP_WORKER_SECRET") or conf().get("amap_worker_secret", "")
        if not worker_secret:
            return ToolResult.fail("amap_worker_secret 未配置，无法使用高德周边搜索")

        try:
            device_code = get_device_code()
        except Exception:
            device_code = "unknown"

        payload = {
            "address": address or None,
            "location": location or None,
            "city": (args.get("city") or "").strip() or None,
            "radius": args.get("radius", 3000),
            "keywords": (args.get("keywords") or "").strip() or None,
            "types": (args.get("types") or "").strip() or None,
            "count": args.get("target_count", 200),
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {worker_secret}",
            "X-Device-Code": device_code,
        }

        try:
            resp = requests.post(
                f"{worker_url.rstrip('/')}/api/amap/nearby_poi",
                json=payload,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.Timeout:
            return ToolResult.fail("amap 服务器响应超时，请稍后再试")
        except requests.ConnectionError:
            return ToolResult.fail("无法连接 amap 服务器，请检查网络")
        except Exception as e:
            logger.error(f"[AmapNearbyPoi] request error: {e}", exc_info=True)
            return ToolResult.fail(f"请求 amap 服务器失败: {e}")

        if resp.status_code == 401:
            return ToolResult.fail("amap worker 鉴权失败，请联系管理员检查配置")

        try:
            data = resp.json()
        except Exception:
            return ToolResult.fail(f"amap 服务器返回非 JSON 响应 (HTTP {resp.status_code})")

        if not data.get("ok"):
            return self._translate_error(data.get("error", {}))

        return ToolResult.success(data["data"])

    def _translate_error(self, error: dict) -> ToolResult:
        code = error.get("code", "INTERNAL_ERROR")
        message = error.get("message", "")
        translated = ERROR_TRANSLATIONS.get(code, "未知错误")

        if code == "BAD_REQUEST" and message:
            translated = f"{translated} — {message}"
        elif code == "AMAP_OTHER_ERROR" and message:
            translated = f"{translated} — {message}"
        elif code == "INTERNAL_ERROR":
            request_id = error.get("request_id", "")
            if request_id:
                translated = f"{translated}（request_id={request_id}）"

        return ToolResult.fail(translated)
