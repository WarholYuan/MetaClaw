# MetaClaw Cloud Client Proxy 设计文档

## 概述

MetaClaw 支持一种"云客户端"部署模式：硬件设备上运行 MetaClaw 轻量实例，提供本地 Web UI，所有 API 请求自动转发到阿里云上的 MetaClaw 服务端。同一套代码，通过配置自动切换行为。

## 自动识别机制

启动时检查 config 中的 `cloud_server_url` 字段：

- **有值且非本机地址** → 自动进入 cloud_mode，API 请求转发到远端
- **没有或为空** → 独立运行（服务端模式）

无需单独的 `cloud_mode` 开关。

### 安装脚本支持

`scripts/install.sh` 新增可选参数：

```bash
# 服务端部署（默认）
curl -fsSL https://.../install.sh | bash

# 客户端部署
curl -fsSL https://.../install.sh | bash -s -- --cloud-server-url http://101.37.126.174:9899
```

安装脚本将 server URL 写入 config.json，客户端启动时自动进入 cloud_mode。

## 模块设计

### 1. 设备码生成 — `common/device.py`

使用 CPU / 硬件序列号生成唯一设备标识。

**跨平台获取策略**：
- macOS: `ioreg -rd1 -c IOPlatformExpertDevice` → `IOPlatformSerialNumber`
- Linux: 读取 `/etc/machine-id`
- Windows: `wmic bios get serialnumber`
- 兜底: 第一个非空 MAC 地址 + hostname 的 SHA256 哈希

**持久化**：首次生成后保存到 `~/.metaclaw/device_id`，后续启动直接读取。

**接口**：
```python
def get_device_code() -> str  # 返回唯一标识字符串
```

### 2. 云代理客户端 — `common/cloud_client.py`

封装对远端 MetaClaw 服务器的 HTTP 请求转发。

**核心职责**：
- 从 config 读取 `cloud_server_url`
- 每个请求自动附带 `X-Device-Code` header
- 支持 SSE streaming 透传（`/stream`、`/api/logs`）
- 支持文件上传透传（`/upload`）
- 支持所有 HTTP 方法（GET / POST / PUT / DELETE）

**需要代理的路由**：
| 路径 | 方法 | 说明 |
|------|------|------|
| `/auth/login` | POST | 认证 |
| `/auth/check` | GET | 认证状态 |
| `/auth/logout` | POST | 登出 |
| `/message` | POST | 发送消息 |
| `/stream` | GET (SSE) | 流式响应 |
| `/poll` | POST | 轮询响应 |
| `/upload` | POST | 文件上传 |
| `/uploads/*` | GET | 上传文件访问（文件在远端） |
| `/api/file` | GET | 文件服务（文件在远端） |
| `/config` | GET/POST | 配置读写 |
| `/api/*` | 全部 | 所有 API（channels, sessions, history, tools, skills, memory, knowledge, scheduler, logs, version, feishu users 等） |

**不代理的路由**（本地服务）：
| 路径 | 说明 |
|------|------|
| `/` | 重定向到 /chat |
| `/chat` | 聊天页面 HTML |
| `/assets/*` | 静态资源（JS/CSS） |

注意：`/uploads/*` 也需要代理，因为文件实际保存在远端服务器上。

**接口**：
```python
class CloudClient:
    def __init__(self, server_url: str, device_code: str)
    def request(self, method: str, path: str, headers: dict, body: bytes) -> requests.Response
    def stream(self, method: str, path: str, headers: dict, body: bytes) -> Iterator[bytes]
```

### 3. WebChannel 集成 — `channel/web/web_channel.py`

在 WebChannel 层增加 cloud_mode 代理逻辑。

**改动点**：

1. **`startup()` 中检测 cloud_mode**：
   - 读取 `cloud_server_url`，判断是否进入 cloud_mode
   - cloud_mode 下初始化 `CloudClient`，日志打印设备码和服务端地址
   - cloud_mode 下跳过 PluginManager 加载和 Bridge 初始化

2. **新增代理 handler 基类 `CloudProxyHandler`**：
   - 通用逻辑：读取请求方法、body、content_type，调用 CloudClient 转发，返回响应
   - SSE 路由（`/stream`、`/api/logs`）使用流式转发
   - 非 SSE 路由使用普通请求转发

3. **路由注册修改**：
   - cloud_mode 下，需要代理的路由指向 `CloudProxyHandler`（或其子类）
   - 本地路由（`/`、`/chat`、`/assets/*`）保持不变

### 4. app.py 启动路径修改

`app.py` 的 `run()` 函数中，cloud_mode 下：

- 只启动 web channel（跳过其他 channel）
- 跳过 `PluginManager().load_plugins()`
- 不初始化 Bridge / Agent

### 5. 安装脚本修改 — `scripts/install.sh`

新增参数解析：

```
--cloud-server-url URL    设置云服务端地址，写入 config.json
```

安装脚本在写入 config.json 时，如果提供了 `--cloud-server-url`，将其加入配置。

### 6. 配置项

在 `config-template.json` 中新增：

```json
{
  "cloud_server_url": ""
}
```

空字符串 = 独立模式。非空且非本机 = cloud_mode。

## 数据流

```
用户浏览器 → 本地 MetaClaw (9899)
  ├── /chat, /assets/* → 本地静态文件（chat.html, JS, CSS）
  └── /message, /api/*, /stream → CloudClient → 远端 MetaClaw (9899)
                                              ↑ Header: X-Device-Code: <device_code>
```

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `common/device.py` | 新增 | 设备码生成与持久化 |
| `common/cloud_client.py` | 新增 | 云 API 代理客户端 |
| `channel/web/web_channel.py` | 修改 | cloud_mode 检测 + 代理 handler |
| `app.py` | 修改 | cloud_mode 启动路径 |
| `config/channel.py` | 修改 | 新增 cloud_server_url 配置项 |
| `scripts/install.sh` | 修改 | 新增 --cloud-server-url 参数 |
| `metaclaw/metaclaw/config-template.json` | 修改 | 新增 cloud_server_url 字段 |

## 错误处理

- **远端不可达**: 返回 `502 Bad Gateway`，前端显示"无法连接到服务器"提示
- **设备码获取失败**: 使用随机 UUID 写入文件，保证有值
- **SSE 流中断**: 前端自动重连机制（已有）
