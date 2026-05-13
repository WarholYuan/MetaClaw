# Cloud Client Proxy 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 MetaClaw 在硬件设备上以轻量客户端模式运行，自动识别并转发所有 API 请求到阿里云服务端。

**Architecture:** 本地 WebChannel 检测 `cloud_server_url` 配置，有值时进入 cloud_mode。本地仅服务 Web UI 静态文件，所有 API 请求通过 `CloudClient` 转发到远端，请求头携带 CPU 序列号生成的设备码。

**Tech Stack:** Python 3, requests (HTTP), web.py (现有), pytest (测试)

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `metaclaw/metaclaw/common/device.py` | 新增 | 跨平台设备码生成与持久化 |
| `metaclaw/metaclaw/common/cloud_client.py` | 新增 | HTTP 代理客户端，转发请求到远端 |
| `metaclaw/metaclaw/channel/web/web_channel.py` | 修改 | cloud_mode 检测 + CloudProxyHandler |
| `metaclaw/metaclaw/app.py` | 修改 | cloud_mode 启动路径优化 |
| `metaclaw/metaclaw/config/channel.py` | 修改 | 新增 `cloud_server_url` 配置项 |
| `metaclaw/metaclaw/config-template.json` | 修改 | 新增 `cloud_server_url` 默认值 |
| `scripts/install.sh` | 修改 | 新增 `--cloud-server-url` 参数 |
| `metaclaw/metaclaw/tests/test_device.py` | 新增 | 设备码测试 |
| `metaclaw/metaclaw/tests/test_cloud_client.py` | 新增 | 云代理客户端测试 |

---

### Task 1: 配置项 — 新增 `cloud_server_url`

**Files:**
- Modify: `metaclaw/metaclaw/config/channel.py:90` (末尾追加)
- Modify: `metaclaw/metaclaw/config-template.json:44` (末尾追加)

- [ ] **Step 1: 在 `config/channel.py` 的 `CHANNEL_SETTINGS` 末尾添加配置项**

在 `web_session_expire_days` 行后添加：

```python
    "cloud_server_url": "",  # 云服务端地址，非空时自动进入 cloud_mode，API 请求转发到该地址
```

- [ ] **Step 2: 在 `config-template.json` 末尾添加默认值**

在 `knowledge` 行后、`}` 前添加：

```json
  "cloud_server_url": ""
```

注意上一行 `web_host` 末尾需要保留逗号。

- [ ] **Step 3: 提交**

```bash
git add metaclaw/metaclaw/config/channel.py metaclaw/metaclaw/config-template.json
git commit -m "feat: add cloud_server_url config setting"
```

---

### Task 2: 设备码生成 — `common/device.py`

**Files:**
- Create: `metaclaw/metaclaw/common/device.py`
- Create: `metaclaw/metaclaw/tests/test_device.py`

- [ ] **Step 1: 编写设备码测试**

创建 `metaclaw/metaclaw/tests/test_device.py`：

```python
import json
import os

from common.device import get_device_code


def test_get_device_code_returns_non_empty_string():
    code = get_device_code()
    assert isinstance(code, str)
    assert len(code) > 0


def test_get_device_code_stable(tmp_path, monkeypatch):
    monkeypatch.setattr("common.device.DEVICE_ID_FILE", str(tmp_path / "device_id"))
    code1 = get_device_code()
    code2 = get_device_code()
    assert code1 == code2


def test_get_device_code_persisted(tmp_path, monkeypatch):
    path = str(tmp_path / "device_id")
    monkeypatch.setattr("common.device.DEVICE_ID_FILE", path)
    code = get_device_code()
    assert os.path.isfile(path)
    with open(path) as f:
        assert f.read().strip() == code


def test_get_device_code_reads_existing(tmp_path, monkeypatch):
    path = str(tmp_path / "device_id")
    with open(path, "w") as f:
        f.write("existing-code-12345")
    monkeypatch.setattr("common.device.DEVICE_ID_FILE", path)
    assert get_device_code() == "existing-code-12345"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/coderhyh/Desktop/yuanhe/MetaClaw/metaclaw && python -m pytest metaclaw/tests/test_device.py -v
```

预期: ImportError — `common.device` 模块不存在。

- [ ] **Step 3: 实现设备码生成**

创建 `metaclaw/metaclaw/common/device.py`：

```python
import hashlib
import os
import platform
import subprocess
import uuid

from common.brand import DEFAULT_ENV_DIR

DEVICE_ID_FILE = os.path.expanduser(f"{DEFAULT_ENV_DIR}/device_id")


def _read_cpu_serial() -> str:
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "IOPlatformSerialNumber" in line:
                    return line.split("=")[-1].strip().strip('"')
        elif system == "Linux":
            for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                if os.path.isfile(path):
                    with open(path) as f:
                        return f.read().strip()
        elif system == "Windows":
            result = subprocess.run(
                ["wmic", "bios", "get", "serialnumber"],
                capture_output=True, text=True, timeout=5,
            )
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            if len(lines) >= 2:
                return lines[1]
    except Exception:
        pass
    return ""


def _generate_device_code() -> str:
    serial = _read_cpu_serial()
    if serial:
        return hashlib.sha256(serial.encode()).hexdigest()[:32]
    host_id = f"{uuid.getnode()}-{platform.node()}"
    return hashlib.sha256(host_id.encode()).hexdigest()[:32]


def get_device_code() -> str:
    path = DEVICE_ID_FILE
    if os.path.isfile(path):
        with open(path, "r") as f:
            code = f.read().strip()
            if code:
                return code
    code = _generate_device_code()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(code)
    return code
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/coderhyh/Desktop/yuanhe/MetaClaw/metaclaw && python -m pytest metaclaw/tests/test_device.py -v
```

预期: 4 个测试全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add metaclaw/metaclaw/common/device.py metaclaw/metaclaw/tests/test_device.py
git commit -m "feat: add device code generation using CPU serial number"
```

---

### Task 3: 云代理客户端 — `common/cloud_client.py`

**Files:**
- Create: `metaclaw/metaclaw/common/cloud_client.py`
- Create: `metaclaw/metaclaw/tests/test_cloud_client.py`

- [ ] **Step 1: 编写云代理客户端测试**

创建 `metaclaw/metaclaw/tests/test_cloud_client.py`：

```python
import json

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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/coderhyh/Desktop/yuanhe/MetaClaw/metaclaw && python -m pytest metaclaw/tests/test_cloud_client.py -v
```

预期: ImportError。

- [ ] **Step 3: 实现云代理客户端**

创建 `metaclaw/metaclaw/common/cloud_client.py`：

```python
import requests as req_lib


class CloudClient:
    def __init__(self, server_url: str, device_code: str):
        self.server_url = server_url.rstrip("/")
        self.device_code = device_code

    def request(self, method: str, path: str, headers: dict | None = None, body: bytes = b"") -> req_lib.Response:
        url = f"{self.server_url}{path}"
        fwd_headers = dict(headers) if headers else {}
        fwd_headers["X-Device-Code"] = self.device_code
        return req_lib.request(method, url, headers=fwd_headers, data=body, timeout=300)

    def stream(self, method: str, path: str, headers: dict | None = None, body: bytes = b""):
        url = f"{self.server_url}{path}"
        fwd_headers = dict(headers) if headers else {}
        fwd_headers["X-Device-Code"] = self.device_code
        resp = req_lib.request(method, url, headers=fwd_headers, data=body, stream=True, timeout=600)
        resp.raise_for_status()
        return resp.iter_content(chunk_size=None)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/coderhyh/Desktop/yuanhe/MetaClaw/metaclaw && python -m pytest metaclaw/tests/test_cloud_client.py -v
```

预期: 5 个测试全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add metaclaw/metaclaw/common/cloud_client.py metaclaw/metaclaw/tests/test_cloud_client.py
git commit -m "feat: add CloudClient for HTTP request proxying"
```

---

### Task 4: WebChannel 集成 — CloudProxyHandler

**Files:**
- Modify: `metaclaw/metaclaw/channel/web/web_channel.py`

这是最核心的改动。在 WebChannel 中添加 cloud_mode 检测和代理 handler。

- [ ] **Step 1: 在 `web_channel.py` 顶部添加导入**

在文件顶部的 import 区域添加：

```python
from common.device import get_device_code
from common.cloud_client import CloudClient
```

- [ ] **Step 2: 添加 cloud_mode 判定和 CloudClient 初始化函数**

在 `_check_auth` 函数之后、`WebMessage` 类之前添加：

```python
def _is_cloud_mode() -> bool:
    url = conf().get("cloud_server_url", "").strip()
    if not url:
        return False
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return host not in ("127.0.0.1", "localhost", "::1", "")


_cloud_client: CloudClient | None = None


def _get_cloud_client() -> CloudClient:
    global _cloud_client
    if _cloud_client is None:
        server_url = conf().get("cloud_server_url", "").strip()
        _cloud_client = CloudClient(server_url, get_device_code())
    return _cloud_client
```

- [ ] **Step 3: 添加 CloudProxyHandler 基类**

在 `AssetsHandler` 类之后（`KnowledgeListHandler` 之前）添加：

```python
class CloudProxyHandler:
    """Proxy handler that forwards requests to the cloud MetaClaw server."""

    STREAM_PATHS = {"/stream", "/api/logs"}

    def _forward(self):
        web.header('Access-Control-Allow-Origin', '*')
        client = _get_cloud_client()
        method = web.ctx.method
        path = web.ctx.path
        query = web.ctx.query or ""
        if query and query.startswith("?"):
            query = query
        full_path = path + query if query else path

        in_headers = dict(web.ctx.env)
        fwd_headers = {}
        if in_headers.get("CONTENT_TYPE"):
            fwd_headers["Content-Type"] = in_headers["CONTENT_TYPE"]
        cookie = web.cookies()
        if cookie.get("metaclaw_auth_token"):
            fwd_headers["Cookie"] = f"metaclaw_auth_token={cookie.get('metaclaw_auth_token')}"

        body = web.data() if method in ("POST", "PUT", "PATCH") else b""

        if full_path in self.STREAM_PATHS:
            return self._forward_stream(client, method, full_path, fwd_headers, body)

        try:
            resp = client.request(method, full_path, fwd_headers, body)
        except Exception:
            web.ctx.status = "502 Bad Gateway"
            web.header('Content-Type', 'application/json; charset=utf-8')
            return json.dumps({"status": "error", "message": "无法连接到云服务器"})

        web.ctx.status = f"{resp.status_code} {resp.reason}"
        for key, value in resp.headers.items():
            if key.lower() not in ("transfer-encoding", "connection", "content-length"):
                web.header(key, value)
        return resp.content

    def _forward_stream(self, client, method, path, headers, body):
        web.header('Content-Type', 'text/event-stream; charset=utf-8')
        web.header('Cache-Control', 'no-cache')
        web.header('X-Accel-Buffering', 'no')
        try:
            chunks = client.stream(method, path, headers, body)
        except Exception:
            web.ctx.status = "502 Bad Gateway"
            return b'data: {"type": "error", "message": "无法连接到云服务器"}\n\n'

        def generate():
            for chunk in chunks:
                yield chunk

        return generate()

    def GET(self, *args):
        return self._forward()

    def POST(self, *args):
        return self._forward()

    def PUT(self, *args):
        return self._forward()

    def DELETE(self, *args):
        return self._forward()
```

- [ ] **Step 4: 修改 `WebChannel.startup()` 中的路由注册**

在 `startup()` 方法中，将 `urls` 元组替换为根据 cloud_mode 动态构建的版本。找到 `urls = (` 行（约第 600 行），替换为：

```python
        if _is_cloud_mode():
            logger.info(f"[WebChannel] ☁️  Cloud Mode — proxying to {conf().get('cloud_server_url')}")
            logger.info(f"[WebChannel] 🔑  Device Code: {get_device_code()}")
            urls = (
                '/', 'RootHandler',
                '/chat', 'ChatHandler',
                '/assets/(.*)', 'AssetsHandler',
                '/auth/login', 'CloudProxyHandler',
                '/auth/check', 'CloudProxyHandler',
                '/auth/logout', 'CloudProxyHandler',
                '/message', 'CloudProxyHandler',
                '/upload', 'CloudProxyHandler',
                '/uploads/(.*)', 'CloudProxyHandler',
                '/api/file', 'CloudProxyHandler',
                '/poll', 'CloudProxyHandler',
                '/stream', 'CloudProxyHandler',
                '/config', 'CloudProxyHandler',
                '/api/channels', 'CloudProxyHandler',
                '/api/weixin/qrlogin', 'CloudProxyHandler',
                '/api/tools', 'CloudProxyHandler',
                '/api/skills', 'CloudProxyHandler',
                '/api/memory', 'CloudProxyHandler',
                '/api/memory/content', 'CloudProxyHandler',
                '/api/knowledge/list', 'CloudProxyHandler',
                '/api/knowledge/read', 'CloudProxyHandler',
                '/api/knowledge/graph', 'CloudProxyHandler',
                '/api/scheduler', 'CloudProxyHandler',
                '/api/sessions', 'CloudProxyHandler',
                '/api/sessions/(.*)/generate_title', 'CloudProxyHandler',
                '/api/sessions/(.*)/clear_context', 'CloudProxyHandler',
                '/api/sessions/(.*)', 'CloudProxyHandler',
                '/api/history', 'CloudProxyHandler',
                '/api/logs', 'CloudProxyHandler',
                '/api/version', 'CloudProxyHandler',
                '/api/feishu/users', 'CloudProxyHandler',
                '/api/feishu/users/(.*)', 'CloudProxyHandler',
            )
        else:
            urls = (
                '/', 'RootHandler',
                '/auth/login', 'AuthLoginHandler',
                '/auth/check', 'AuthCheckHandler',
                '/auth/logout', 'AuthLogoutHandler',
                '/message', 'MessageHandler',
                '/upload', 'UploadHandler',
                '/uploads/(.*)', 'UploadsHandler',
                '/api/file', 'FileServeHandler',
                '/poll', 'PollHandler',
                '/stream', 'StreamHandler',
                '/chat', 'ChatHandler',
                '/config', 'ConfigHandler',
                '/api/channels', 'ChannelsHandler',
                '/api/weixin/qrlogin', 'WeixinQrHandler',
                '/api/tools', 'ToolsHandler',
                '/api/skills', 'SkillsHandler',
                '/api/memory', 'MemoryHandler',
                '/api/memory/content', 'MemoryContentHandler',
                '/api/knowledge/list', 'KnowledgeListHandler',
                '/api/knowledge/read', 'KnowledgeReadHandler',
                '/api/knowledge/graph', 'KnowledgeGraphHandler',
                '/api/scheduler', 'SchedulerHandler',
                '/api/sessions', 'SessionsHandler',
                '/api/sessions/(.*)/generate_title', 'SessionTitleHandler',
                '/api/sessions/(.*)/clear_context', 'SessionClearContextHandler',
                '/api/sessions/(.*)', 'SessionDetailHandler',
                '/api/history', 'HistoryHandler',
                '/api/logs', 'LogsHandler',
                '/api/version', 'VersionHandler',
                '/api/feishu/users', 'FeishuUsersHandler',
                '/api/feishu/users/(.*)', 'FeishuUserDetailHandler',
                '/assets/(.*)', 'AssetsHandler',
            )
```

注意：cloud_mode 下的 `ChatHandler` 和 `AssetsHandler` 仍然使用本地 handler（不需要改），但其余全部指向 `CloudProxyHandler`。

- [ ] **Step 5: 提交**

```bash
git add metaclaw/metaclaw/channel/web/web_channel.py
git commit -m "feat: add CloudProxyHandler and cloud_mode routing in WebChannel"
```

---

### Task 5: app.py 启动路径优化

**Files:**
- Modify: `metaclaw/metaclaw/app.py`

- [ ] **Step 1: 修改 `run()` 函数，cloud_mode 下跳过不必要的初始化**

在 `run()` 函数中，找到 `raw_channel = conf().get("channel_type", "web")` 行（约第 272 行），在其之后添加 cloud_mode 检测：

```python
        # Parse channel_type into a list
        raw_channel = conf().get("channel_type", "web")

        # Cloud mode: only start web channel, skip plugins and other channels
        cloud_server_url = conf().get("cloud_server_url", "").strip()
        if cloud_server_url:
            from urllib.parse import urlparse
            parsed = urlparse(cloud_server_url)
            host = parsed.hostname or ""
            if host not in ("127.0.0.1", "localhost", "::1", ""):
                logger.info(f"[App] ☁️  Cloud mode detected, server: {cloud_server_url}")
                channel_names = ["web"]
                _channel_mgr = ChannelManager()
                _channel_mgr.cloud_mode = True
                _channel_mgr.start(channel_names, first_start=False)
                while True:
                    time.sleep(1)
                return
```

这段代码在 config 加载完成后、channel_type 解析之后执行。如果检测到非本机的 `cloud_server_url`，直接启动 web channel 并跳过 PluginManager 加载，然后进入主循环。

- [ ] **Step 2: 提交**

```bash
git add metaclaw/metaclaw/app.py
git commit -m "feat: skip heavy initialization in cloud mode startup"
```

---

### Task 6: 安装脚本 — 新增 `--cloud-server-url` 参数

**Files:**
- Modify: `scripts/install.sh`

- [ ] **Step 1: 添加变量和参数解析**

在脚本变量定义区（约第 25 行 `DEV_INSTALL=` 之后）添加：

```bash
CLOUD_SERVER_URL="${METACLAW_CLOUD_SERVER_URL:-}"
```

在 `while` 参数解析循环中（`--no-shims` 行之后，`*)` 行之前）添加：

```bash
    --cloud-server-url) CLOUD_SERVER_URL="${2:?--cloud-server-url requires a URL}"; shift 2 ;;
```

- [ ] **Step 2: 修改 usage 函数**

在 `usage()` 函数的 Options 区域添加：

```
  --cloud-server-url URL   Cloud server URL for client mode (writes to config)
```

在 Environment overrides 中添加：

```
  METACLAW_CLOUD_SERVER_URL
```

- [ ] **Step 3: 在 config 写入 Python 脚本中添加 cloud_server_url**

找到 `step "Configuring workspace..."` 下的 Python 内联脚本（约第 186-203 行），在 `config["service_log_file"]` 行之后添加：

```python
if os.environ.get("CLOUD_SERVER_URL"):
    config["cloud_server_url"] = os.environ["CLOUD_SERVER_URL"]
```

同时在 Python 脚本上方的环境变量传递中，将 `CLOUD_SERVER_URL` 传入：

将：
```bash
CONFIG_FILE="$CONFIG_FILE" WORKSPACE_DIR="$WORKSPACE_DIR" python - <<'PY'
```

改为：
```bash
CONFIG_FILE="$CONFIG_FILE" WORKSPACE_DIR="$WORKSPACE_DIR" CLOUD_SERVER_URL="$CLOUD_SERVER_URL" python - <<'PY'
```

- [ ] **Step 4: 在 install.env 中保存**

在 `write_install_env` 函数中添加：

```bash
  write_install_env_var METACLAW_CLOUD_SERVER_URL "$CLOUD_SERVER_URL"
```

- [ ] **Step 5: 提交**

```bash
git add scripts/install.sh
git commit -m "feat: add --cloud-server-url option to install script"
```

---

### Task 7: 集成验证

- [ ] **Step 1: 运行全部测试确保无回归**

```bash
cd /Users/coderhyh/Desktop/yuanhe/MetaClaw/metaclaw && python -m pytest metaclaw/tests/ -v
```

预期: 所有测试 PASS（包括新增的 test_device.py 和 test_cloud_client.py）。

- [ ] **Step 2: 本地启动验证独立模式（默认）**

```bash
cd /Users/coderhyh/Desktop/yuanhe/MetaClaw/metaclaw && python -m app
```

确认日志中没有出现 "Cloud Mode" 字样，正常以独立模式启动。

- [ ] **Step 3: 本地启动验证 cloud_mode**

临时在 config 中设置 `"cloud_server_url": "http://101.37.126.174:9899"`，启动后确认日志输出：
- `[App] ☁️  Cloud mode detected`
- `[WebChannel] ☁️  Cloud Mode — proxying to http://101.37.126.174:9899`
- `[WebChannel] 🔑  Device Code: <32位hex>`

访问 `http://localhost:9899/chat` 确认 Web UI 正常加载，API 请求被转发到远端。

- [ ] **Step 4: 恢复 config 并最终提交**

恢复 config.json 中的 `cloud_server_url` 为空，确保不影响后续开发。

```bash
git add -A
git commit -m "feat: complete cloud client proxy implementation"
```
