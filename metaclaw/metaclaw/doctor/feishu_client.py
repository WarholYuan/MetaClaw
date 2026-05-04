"""Lightweight Feishu client for Metadoctor.

Reuses lark-oapi for WebSocket and REST API for sending messages.
Uses a separate Feishu app from MetaClaw's main channel.
"""

import importlib
import json
import os
import threading
import time

import requests

from common.log import logger

# Lazy-check for lark_oapi SDK availability (same pattern as feishu_channel.py)
LARK_SDK_AVAILABLE = importlib.util.find_spec("lark_oapi") is not None
lark = None


def _ensure_lark_imported():
    """Import lark_oapi on first use."""
    global lark
    if lark is None:
        import lark_oapi as _lark
        lark = _lark
    return lark


class MetadoctorFeishuClient:
    """Feishu client for Metadoctor: receive messages via WebSocket, reply via REST API."""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token_cache = (None, 0)  # (token, expire_time)
        self._ws_client = None
        self._ws_thread = None
        self._processed_msg_ids = set()  # dedup set
        self._processed_lock = threading.Lock()

    def get_token(self) -> str:
        """Fetch tenant access token with 10-minute cache."""
        token, expire = self._token_cache
        if token and time.time() < expire - 60:
            return token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        headers = {"Content-Type": "application/json"}
        body = {"app_id": self.app_id, "app_secret": self.app_secret}
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    token = data.get("tenant_access_token")
                    expire_in = data.get("expire", 7200)
                    self._token_cache = (token, time.time() + expire_in)
                    return token
                logger.error(f"[Metadoctor] get token error: code={data.get('code')}, msg={data.get('msg')}")
            else:
                logger.error(f"[Metadoctor] fetch token HTTP error: {resp.status_code}")
        except Exception as e:
            logger.error(f"[Metadoctor] fetch token exception: {e}")
        return ""

    def send_text(self, open_id: str, text: str) -> bool:
        """Send a text message to a user by open_id."""
        token = self.get_token()
        if not token:
            logger.error("[Metadoctor] Cannot send message: no access token")
            return False

        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "receive_id": open_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=body,
                params={"receive_id_type": "open_id"},
                timeout=(5, 10),
            )
            data = resp.json()
            if data.get("code") == 0:
                logger.info(f"[Metadoctor] send text message ok")
                return True
            logger.error(f"[Metadoctor] send text failed: code={data.get('code')}, msg={data.get('msg')}")
        except Exception as e:
            logger.error(f"[Metadoctor] send text exception: {e}")
        return False

    def start_websocket(self, on_message):
        """Start WebSocket listener in a background thread.

        on_message(open_id: str, text: str) will be called for each text message.
        """
        if not LARK_SDK_AVAILABLE:
            logger.error("[Metadoctor] lark_oapi not installed, cannot start WebSocket")
            raise ImportError("lark_oapi not installed")

        _ensure_lark_imported()

        def _dedup(msg_id: str) -> bool:
            """Return True if message should be processed (not a duplicate)."""
            with self._processed_lock:
                if msg_id in self._processed_msg_ids:
                    return False
                self._processed_msg_ids.add(msg_id)
                # Trim set if it grows too large (simple eviction)
                if len(self._processed_msg_ids) > 5000:
                    self._processed_msg_ids = set(list(self._processed_msg_ids)[-2000:])
                return True

        def handle_message_event(data) -> None:
            try:
                event_dict = json.loads(lark.JSON.marshal(data))
                event = event_dict.get("event", {})
                msg = event.get("message", {})

                # Only handle text messages
                if msg.get("message_type") != "text":
                    return

                # Deduplicate by message_id
                msg_id = msg.get("message_id")
                if not msg_id or not _dedup(msg_id):
                    return

                # Parse message content
                content = json.loads(msg.get("content", "{}"))
                text = content.get("text", "").strip()
                if not text:
                    return

                sender = event.get("sender", {})
                sender_id = sender.get("sender_id", {})
                open_id = sender_id.get("open_id")
                if not open_id:
                    return

                logger.info(f"[Metadoctor] received message from {open_id}: {text[:50]}")
                on_message(open_id, text)

            except Exception as e:
                logger.error(f"[Metadoctor] websocket handle error: {e}", exc_info=True)

        def handle_read_event(data) -> None:
            pass  # ignore read receipts

        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(handle_message_event) \
            .register_p2_im_message_message_read_v1(handle_read_event) \
            .build()

        def start_client():
            import asyncio
            import ssl as ssl_module

            original_create_default_context = ssl_module.create_default_context

            def create_unverified_context(*args, **kwargs):
                ctx = original_create_default_context(*args, **kwargs)
                ctx.check_hostname = False
                ctx.verify_mode = ssl_module.CERT_NONE
                return ctx

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                import lark_oapi.ws.client as _ws_mod
                _ws_mod.loop = loop
            except Exception:
                pass

            startup_error = None
            for attempt in range(2):
                try:
                    if attempt == 1:
                        logger.warning("[Metadoctor] Retrying with SSL verification disabled...")
                        ssl_module.create_default_context = create_unverified_context
                        ssl_module._create_unverified_context = create_unverified_context

                    ws_client = lark.ws.Client(
                        self.app_id,
                        self.app_secret,
                        event_handler=event_handler,
                        log_level=lark.LogLevel.WARNING,
                    )
                    self._ws_client = ws_client
                    logger.info("[Metadoctor] WebSocket client starting...")
                    ws_client.start()
                    break

                except (SystemExit, KeyboardInterrupt):
                    logger.info("[Metadoctor] WebSocket received stop signal")
                    break
                except Exception as e:
                    error_msg = str(e)
                    is_ssl = "CERTIFICATE_VERIFY_FAILED" in error_msg or "certificate verify failed" in error_msg.lower()
                    if is_ssl and attempt == 0:
                        logger.warning(f"[Metadoctor] SSL error, retrying...")
                        continue
                    logger.error(f"[Metadoctor] WebSocket client error: {e}", exc_info=True)
                    startup_error = error_msg
                    ssl_module.create_default_context = original_create_default_context
                    break

            try:
                loop.close()
            except Exception:
                pass
            logger.info("[Metadoctor] WebSocket thread exited")

        self._ws_thread = threading.Thread(target=start_client, daemon=True)
        self._ws_thread.start()
        logger.info("[Metadoctor] WebSocket thread started")
        return self._ws_thread

    def stop(self):
        """Stop the WebSocket client and thread."""
        import ctypes
        ws_client = self._ws_client
        self._ws_client = None
        ws_thread = self._ws_thread
        self._ws_thread = None
        if ws_thread and ws_thread.is_alive():
            try:
                tid = ws_thread.ident
                if tid:
                    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                        ctypes.c_ulong(tid), ctypes.py_object(SystemExit)
                    )
                    if res == 1:
                        logger.info("[Metadoctor] Interrupted ws thread via ctypes")
                    elif res > 1:
                        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), None)
            except Exception as e:
                logger.warning(f"[Metadoctor] Error interrupting ws thread: {e}")
