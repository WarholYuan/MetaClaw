# MetaClaw AMap 周边搜索 Cloudflare Worker 设计文档

## 概述

为 MetaClaw 引入"基于地理位置的周边商家查询"能力。当用户在 MetaClaw 对话里问"附近有什么商家"这类问题时，LLM 自动调用 `amap_nearby_poi` tool，由阿里云中央 MetaClaw 转发请求到 Cloudflare Worker，Worker 持有高德 API key 并调用高德 Web 服务 API，返回 POI 列表。

**核心约束**：
- 高德 API key 仅存在于 Cloudflare Worker Secrets，阿里云中央和客户私有化部署的 MetaClaw 都拿不到 key
- 客户零额外配置：`scripts/install.sh` 自动写默认值
- 仅在 LLM 判断为地理相关问题时才调用高德，非相关问题不消耗高德额度
- Worker 代码在 MetaClaw 仓库 `worker/amap/` 子目录，单仓库管理，wrangler 独立部署到 Cloudflare 边缘
- 阿里云中央 → Cloudflare Worker 用 Bearer Token 鉴权（共享密钥）
- 客户 → 阿里云中央复用现有 cloud_mode + 设备码鉴权

## 目标与非目标

### 目标（第一版必做）

1. 在 `worker/amap/` 子目录创建 Cloudflare Worker（TypeScript + Hono + wrangler），暴露 `POST /api/amap/nearby_poi`
2. Worker 内部自动串接高德 v3 geocode + v5 place/around，对外仅暴露一个 endpoint
3. 在 `metaclaw/agent/tools/amap/` 下注册 `amap_nearby_poi` tool，LLM function calling 自动选择
4. 阿里云中央 MetaClaw 作为中间层：接收 LLM tool 调用 → 转发到 Cloudflare Worker → 返回结果
5. 错误标准化：所有高德侧错误 / 网络错误 / 参数错误转成统一 ErrorCode，Tool 端翻译成中文给最终用户
6. 沿用棉花糖已验证的关键算法：infocode=10021 退避重试、500ms 节流、POI id 去重、距离排序、`show_fields=business`、normalizePoi 字段拍平
7. install.sh 复用 `--cloud-server-url` 参数同时写入 `cloud_server_url` 和 `amap_worker_url`，客户命令零改动

### 非目标（第一版明确不做）

- ❌ 高德其他 API（路径规划、天气、交通、文本搜索 POI 等）
- ❌ 设备码白名单 / 黑名单拦截
- ❌ 按设备码计量计费 / 限流（MetaClaw 已有 per-device 计数，未来加用）
- ❌ HMAC 请求签名（设备码够用即停）
- ❌ 缓存（同坐标短时间复用）
- ❌ 自定义域名（第一版用 workers.dev 默认域名）
- ❌ 多租户隔离（KV、计费、tenant 字段等）
- ❌ 性能压测、跨区域延迟测试

## 整体架构

```
客户机器（cloud_mode = True，本地端口 9899）：

    用户在浏览器输入："附近 3 公里有什么咖啡店"
                          ↓
    Customer MetaClaw（轻量客户端）
      - LLM/tools 都不在这跑
      - 任何 /api/* 请求 → CloudProxyHandler 透传
      - CloudClient 自动加 X-Device-Code header
                          ↓ HTTPS POST /api/chat
                          ↓ X-Device-Code: <设备码 hash>
                          ↓
中央 MetaClaw（standalone，101.37.126.174:9899）：

    /api/chat → ChatHandler → Agent → LLM (with tools)
                                  ↓
                   LLM 看到 amap_nearby_poi tool 描述
                   判断"附近 3 公里咖啡店"是地理问题
                   输出 function call: amap_nearby_poi(...)
                                  ↓
                   AmapNearbyPoi.execute()
                     - 读 amap_worker_url（Cloudflare Worker 地址）
                     - 读 AMAP_WORKER_SECRET
                     - POST Cloudflare Worker /api/amap/nearby_poi
                       Authorization: Bearer <AMAP_WORKER_SECRET>
                       X-Device-Code: <设备码>（透传，用于日志）
                                  ↓
Cloudflare Worker（metaclaw-amap.xxx.workers.dev）：

    Hono 路由 POST /api/amap/nearby_poi
      - 校验 Authorization Bearer Token
      - 记录 X-Device-Code（仅日志）
      - 从 Worker Secrets 读 AMAP_WEB_SERVICE_KEY
      - 调高德 v3 geocode（如需）
      - 调高德 v5 /place/around（分页 + 节流 + 重试）
      - normalize + 去重 + 排序 + summary
      - 返回标准化 JSON
                                  ↓
                   LLM 拿到 POI 数据 → 组织自然语言回答
                                  ↓
                   /api/chat 返回客户

高德 Web 服务 API（出站）：
    /v3/geocode/geo
    /v5/place/around
```

**三种用户提问的链路对照：**

| 用户问题 | LLM 调 tool | Cloudflare Worker 被打到 |
|---|---|---|
| "你叫什么名字" | 不调任何 tool | ❌ 否 |
| "现在比特币多少钱" | 调 web_search | ❌ 否 |
| "附近 3 公里有什么咖啡店" | 调 amap_nearby_poi | ✅ 是 |

> 客户每条消息都过中央 `/api/chat`（cloud_mode 现有行为），但 Cloudflare Worker 仅在 LLM 选择 amap tool 时被打到。

## 核心组件

### 1. Cloudflare Worker — `worker/amap/`

#### 1.1 文件布局

```
worker/amap/
├── package.json         # dependencies: hono, wrangler (devDep)
├── tsconfig.json
├── wrangler.toml        # name = "metaclaw-amap", compatibility_date, [vars], secrets
├── src/
│   ├── index.ts         # Hono app 入口 + 路由注册
│   ├── routes/
│   │   └── nearby-poi.ts    # POST /api/amap/nearby_poi handler
│   ├── services/
│   │   ├── geocode.ts       # 高德 v3 geocode
│   │   ├── around.ts        # 高德 v5 /place/around 分页 + 重试
│   │   └── normalize.ts     # POI 字段拍平 + 去重 + 排序 + summary
│   ├── middleware/
│   │   └── auth.ts          # Bearer Token 校验中间件
│   ├── errors.ts            # ErrorCode 常量 + AmapError 类
│   └── types.ts             # 请求/响应类型定义
└── tests/
    ├── nearby-poi.test.ts
    ├── geocode.test.ts
    ├── around.test.ts
    └── normalize.test.ts
```

#### 1.2 wrangler.toml

```toml
name = "metaclaw-amap"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[vars]
ENVIRONMENT = "production"

# Secrets (通过 wrangler secret put 设置，不写入代码):
# - AMAP_WEB_SERVICE_KEY: 高德 Web 服务 key
# - WORKER_AUTH_SECRET: Bearer Token 共享密钥
```

#### 1.3 入口 src/index.ts

```typescript
import { Hono } from 'hono'
import { authMiddleware } from './middleware/auth'
import { nearbyPoi } from './routes/nearby-poi'

type Bindings = {
  AMAP_WEB_SERVICE_KEY: string
  WORKER_AUTH_SECRET: string
}

const app = new Hono<{ Bindings: Bindings }>()

app.use('/api/*', authMiddleware)
app.post('/api/amap/nearby_poi', nearbyPoi)

export default app
```

#### 1.4 middleware/auth.ts

```typescript
import { Context, Next } from 'hono'

export async function authMiddleware(c: Context, next: Next) {
  const authHeader = c.req.header('Authorization') || ''
  const token = authHeader.replace('Bearer ', '')

  if (!token || token !== c.env.WORKER_AUTH_SECRET) {
    return c.json({
      ok: false,
      error: { code: 'UNAUTHORIZED', message: 'Invalid or missing auth token', retryable: false }
    }, 401)
  }

  await next()
}
```

#### 1.5 routes/nearby-poi.ts 核心流程

```typescript
export async function nearbyPoi(c: Context) {
  const requestId = crypto.randomUUID()
  const deviceCode = c.req.header('X-Device-Code') || 'anonymous'

  // 1. 解析请求体
  const body = await c.req.json()

  // 2. 参数校验（address/location 二选一、radius 范围、count 范围）
  const validated = validateRequest(body)
  if (validated.error) {
    return c.json({ ok: false, request_id: requestId, error: { code: 'BAD_REQUEST', message: validated.error, retryable: false } })
  }

  // 3. 拿中心点
  let location = validated.location
  if (!location) {
    const geo = await geocode(validated.address!, validated.city, c.env.AMAP_WEB_SERVICE_KEY)
    location = geo.location
  }

  // 4. 分页拉 /place/around
  const rawPois = await queryAround({
    key: c.env.AMAP_WEB_SERVICE_KEY,
    location,
    radius: validated.radius,
    targetCount: validated.count,
    keywords: validated.keywords,
    types: validated.types,
  })

  // 5. 后处理
  const rows = normalize(rawPois)
  const deduped = dedupe(rows)
  const sorted = sortByDistance(deduped)
  const summary = buildSummary(sorted)

  return c.json({
    ok: true,
    request_id: requestId,
    data: { center: { location, ... }, query: { ... }, unique_count: sorted.length, rows: sorted, summary }
  })
}
```

#### 1.6 services/around.ts 关键逻辑

```typescript
const AMAP_AROUND_URL = 'https://restapi.amap.com/v5/place/around'
const PAGE_SIZE = 25

export async function queryAround(opts: AroundOptions): Promise<RawPoi[]> {
  const pages = Math.ceil(opts.targetCount / PAGE_SIZE)
  const allPois: RawPoi[] = []

  for (let page = 1; page <= pages; page++) {
    const params = new URLSearchParams({
      key: opts.key,
      location: opts.location,
      radius: String(opts.radius),
      page_size: String(PAGE_SIZE),
      page_num: String(page),
      show_fields: 'business',
    })
    if (opts.keywords) params.set('keywords', opts.keywords)
    if (opts.types) params.set('types', opts.types)

    const data = await fetchWithRetry(`${AMAP_AROUND_URL}?${params}`)
    const pois = data.pois || []
    allPois.push(...pois)

    if (pois.length < PAGE_SIZE) break
    if (page < pages) {
      await sleep(pages > 20 ? 100 : 500)
    }
  }

  return allPois
}

async function fetchWithRetry(url: string, retries = 3, delayMs = 1200): Promise<any> {
  for (let i = 0; i <= retries; i++) {
    const resp = await fetch(url)
    const data = await resp.json()

    if (data.infocode === '10021') {
      if (i === retries) throw new AmapError('AMAP_QPS_EXCEEDED', '高德接口限流', true)
      await sleep(delayMs * Math.pow(1.5, i))
      continue
    }

    if (INFOCODE_MAP[data.infocode]) {
      throw new AmapError(INFOCODE_MAP[data.infocode], data.info || '高德返回错误', false)
    }

    if (data.infocode !== '1' && data.infocode !== '10000') {
      throw new AmapError('AMAP_OTHER_ERROR', `高德返回: ${data.info}`, false)
    }

    return data
  }
}
```

### 2. 客户端 Tool — `metaclaw/agent/tools/amap/`

#### 2.1 文件布局

```
metaclaw/agent/tools/amap/
├── __init__.py          # 留空或导出 AmapNearbyPoi
└── amap_nearby_poi.py   # AmapNearbyPoi(BaseTool) 类定义
```

#### 2.2 类骨架（基于 WebSearch 模板）

```python
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
            "address":      {"type": "string", "description": "..."},
            "location":     {"type": "string", "description": "lng,lat 格式"},
            "city":         {"type": "string", "description": "address 模式下的城市 hint"},
            "radius":       {"type": "integer", "description": "1-50000，默认 3000"},
            "keywords":     {"type": "string"},
            "types":        {"type": "string"},
            "target_count": {"type": "integer", "description": "1-1000，默认 200"},
        },
        "required": []
    }

    @staticmethod
    def is_available() -> bool:
        return bool(
            os.environ.get("AMAP_WORKER_URL")
            or conf().get("amap_worker_url", "")
        )

    def execute(self, args: dict) -> ToolResult: ...
```

#### 2.3 execute() 流程

1. 校验：`address` 与 `location` 至少一个非空，否则 `ToolResult.fail("地址或经纬度至少要给一个")`
2. 读 `amap_worker_url`：env 优先，fallback 到 `conf().get("amap_worker_url")`，空则 fail
3. 读 `AMAP_WORKER_SECRET`：env 获取，空则 fail（"AMAP_WORKER_SECRET 未配置"）
4. 取设备码：`get_device_code()`
5. 拼请求体和 headers：
   - `Authorization: Bearer <AMAP_WORKER_SECRET>`
   - `X-Device-Code: <设备码>`（透传给 Worker 做日志）
6. `requests.post(f"{worker_url}/api/amap/nearby_poi", ..., timeout=30)`
7. 处理网络层异常：`requests.Timeout` / `ConnectionError` / 其他
8. 处理 HTTP 状态码：401 → "amap worker 鉴权失败，请检查 AMAP_WORKER_SECRET"；非 200 → 透传错误
9. 解析 JSON，校验 `ok` 字段
10. `ok: false` → 调 `_translate_error()` 把 ErrorCode 翻成中文
11. `ok: true` → `ToolResult.success(payload["data"])`

#### 2.4 错误码 → 中文翻译表

| ErrorCode | 中文 ToolResult 文案 |
|---|---|
| `UNAUTHORIZED` | "amap worker 鉴权失败，请联系管理员检查配置" |
| `BAD_REQUEST` | "请求参数错误 — {message}" |
| `GEOCODE_NO_RESULT` | "找不到这个地点，请提供更具体的地址或直接给经纬度" |
| `AMAP_QPS_EXCEEDED` | "高德接口繁忙，请稍后再问" |
| `AMAP_QUOTA_EXCEEDED` | "高德今日额度已用尽，请明日再试或联系管理员" |
| `AMAP_KEY_INVALID` | "amap worker 内部 key 异常，请联系管理员" |
| `AMAP_OTHER_ERROR` | "高德返回错误 — {message}" |
| `UPSTREAM_TIMEOUT` | "高德接口超时，请稍后再问" |
| `INTERNAL_ERROR` | "amap worker 内部错误（request_id={id}）" |

#### 2.5 注册到 ToolManager

`metaclaw/agent/tools/__init__.py` 的 `_import_optional_tools()` 内追加：

```python
try:
    from agent.tools.amap.amap_nearby_poi import AmapNearbyPoi
    tools['AmapNearbyPoi'] = AmapNearbyPoi
except ImportError as e:
    logger.error(f"[Tools] AmapNearbyPoi not loaded - missing dependency: {e}")
except Exception as e:
    logger.error(f"[Tools] AmapNearbyPoi failed to load: {e}")
```

`__all__` 追加 `'AmapNearbyPoi'`。`is_available()` 返回 False 时 ToolManager 仍会加载类，但 LLM 在 missing config 时 execute 会立即 fail——属于自然降级。

### 3. 阿里云中央 MetaClaw 改动

中央 MetaClaw 在这个方案里**不再直接调高德 API**，它的角色是：
- 运行 LLM + tools
- 当 LLM 选择 `amap_nearby_poi` tool 时，Tool 的 `execute()` 发 HTTP 到 Cloudflare Worker
- per-device 计数（已有 `_log_device_code`）自动覆盖

**需要改动的文件：**

#### 3.1 config/channel.py 默认值

```python
"amap_worker_url": "",  # Cloudflare Worker 地址，留空则禁用 amap_nearby_poi tool
```

#### 3.2 中央服务器 env

```bash
AMAP_WORKER_URL=https://metaclaw-amap.xxx.workers.dev
AMAP_WORKER_SECRET=<与 Cloudflare Worker 共享的密钥>
```

#### 3.3 web_channel.py 不需要改动

- Tool 的 `execute()` 是 outbound HTTP 调 Cloudflare Worker，不经过本地路由
- 不需要在 web_channel.py 加 `/api/amap/nearby_poi` 路由
- `_log_device_code` processor 已经在 `/api/chat` 层面记录 per-device 计数

### 4. 客户侧——无需改动

客户侧 MetaClaw 运行在 cloud_mode 下，**所有 `/api/chat` 请求都透传到阿里云中央**。LLM 和 tools 都在中央跑，客户侧根本不执行 `amap_nearby_poi` tool。因此：

- 客户侧**不需要** `AMAP_WORKER_URL` 或 `AMAP_WORKER_SECRET` 环境变量
- 客户侧**不需要** `amap_worker_url` 配置项
- install.sh **不需要改动**

客户安装命令**完全不变**：

```bash
curl -fsSL https://.../install.sh | bash -s -- \
  --cloud-server-url http://101.37.126.174:9899
```

> 客户的 cloud_mode MetaClaw 只是个透传代理，amap 能力完全由中央服务器提供。客户装完即用，零感知。

## 接口协议

### Endpoint（Cloudflare Worker 对外）

```
POST https://metaclaw-amap.xxx.workers.dev/api/amap/nearby_poi
Content-Type: application/json
Authorization: Bearer <AMAP_WORKER_SECRET>
X-Device-Code: <32 字符设备码 hash>（可选，仅日志用）
```

### 请求体

```json
{
  "address": "杭州未来研创园",
  "location": null,
  "city": "杭州",
  "radius": 10000,
  "keywords": "餐饮",
  "types": null,
  "count": 200
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `address` | string \| null | address/location 二选一 | — | 地名/地址 |
| `location` | string \| null | 同上 | — | `"lng,lat"`，优先级高于 address |
| `city` | string \| null | 否 | null | 仅 address 模式下用作 geocode hint |
| `radius` | integer | 否 | 3000 | 搜索半径米，[1, 50000] |
| `keywords` | string \| null | 否 | null | 模糊关键字，如"餐饮""咖啡" |
| `types` | string \| null | 否 | null | POI 类型代码；跟 keywords 同传时按高德默认行为（types 优先） |
| `count` | integer | 否 | 200 | 目标拉取条数 [1, 1000]，自动折算分页 |

### 响应体（成功）

```json
{
  "ok": true,
  "request_id": "uuid-xxx",
  "data": {
    "center": {
      "formatted_address": "浙江省杭州市余杭区未来研创园",
      "location": "120.037925,30.245525",
      "city": "杭州市",
      "district": "余杭区"
    },
    "query": {
      "radius_m": 10000,
      "keywords": "餐饮",
      "types": null,
      "count": 200
    },
    "unique_count": 187,
    "rows": [
      {
        "id": "B0FFGXXXXX",
        "name": "星巴克(未来研创园店)",
        "category": "咖啡厅",
        "type": "餐饮服务;咖啡厅",
        "typecode": "050500",
        "distance_m": 142,
        "address": "梦想小镇互联网村 X 幢",
        "province": "浙江省",
        "city": "杭州市",
        "district": "余杭区",
        "business_area": "仓前",
        "rating": "4.6",
        "cost": "35",
        "tel": "0571-XXXXXXXX",
        "open_time": "周一至周日 07:00-22:00",
        "tag": "美式咖啡;拿铁",
        "location": "120.038000,30.245600"
      }
    ],
    "summary": {
      "nearest_10": [],
      "category_top_15": [
        {"category": "中餐厅", "count": 42},
        {"category": "快餐厅", "count": 31}
      ]
    }
  }
}
```

### 响应体（失败）

```json
{
  "ok": false,
  "request_id": "uuid-xxx",
  "error": {
    "code": "AMAP_QPS_EXCEEDED",
    "message": "高德接口限流，请稍后重试",
    "retryable": true,
    "details": {"infocode": "10021"}
  }
}
```

### 错误码完整表

| ErrorCode | HTTP 状态 | 含义 | retryable |
|---|---|---|---|
| `UNAUTHORIZED` | 401 | Bearer Token 无效或缺失 | false |
| `BAD_REQUEST` | 400 | 参数缺失/越界 | false |
| `GEOCODE_NO_RESULT` | 200 | geocode 找不到地址 | false |
| `AMAP_QPS_EXCEEDED` | 200 | 高德 10021 重试 N 次仍失败 | true |
| `AMAP_QUOTA_EXCEEDED` | 200 | 高德 10003/10004 配额用尽 | false |
| `AMAP_KEY_INVALID` | 200 | 高德 10001/10009 key 失效 | false |
| `AMAP_OTHER_ERROR` | 200 | 其他 infocode | false |
| `UPSTREAM_TIMEOUT` | 504 | 调高德超时 | true |
| `INTERNAL_ERROR` | 500 | Worker 自身 bug | false |

> **设计原则**：401/400 用 HTTP 状态码做协议层拦截。所有跟高德相关的业务错误一律走 HTTP 200 + `ok: false`，Tool 端只解析 JSON body 即可。

## 鉴权模型

### 双层鉴权

```
客户 MetaClaw ──[X-Device-Code]──▶ 阿里云中央 MetaClaw
                                         │
                                         ▼ Tool execute()
                              [Authorization: Bearer <secret>]
                              [X-Device-Code: <透传>]
                                         │
                                         ▼
                           Cloudflare Worker
```

**第一层：客户 → 阿里云中央**
- 使用 X-Device-Code header（现有 cloud_mode 机制）
- 第一版仅记录，不阻断
- `_log_device_code` 已在 `api_counts.json` 记录每个设备的调用数

**第二层：阿里云中央 → Cloudflare Worker**
- 使用 `Authorization: Bearer <AMAP_WORKER_SECRET>`
- Worker 端严格校验：token 不匹配直接返回 401
- 这个 secret 只有阿里云中央知道，客户端完全不接触

### 安全边界

**能挡的：**
- 陌生人直接调 Cloudflare Worker → 401（没有 Bearer Token）
- 陌生人扫到阿里云 IP → 不知道 Cloudflare Worker 地址，且即使知道也没有 secret

**挡不住的：**
- 阿里云中央服务器被入侵 → 攻击者拿到 AMAP_WORKER_SECRET
- 升级路径：加 IP 白名单（Cloudflare Access）或 mTLS

## Worker 内部逻辑流程

```
1. 入口鉴权
   ├─ 校验 Authorization: Bearer <token>
   │   └─ 不匹配 → 401 UNAUTHORIZED
   └─ 记录 X-Device-Code（仅日志）

2. 解析请求体
   ├─ JSON.parse(body) → 失败 400 BAD_REQUEST
   └─ 生成 request_id (crypto.randomUUID())

3. 参数规范化与校验
   ├─ address 和 location 都没传 → BAD_REQUEST
   ├─ location 格式校验 "lng,lat" → BAD_REQUEST
   ├─ radius 不在 [1, 50000] → BAD_REQUEST
   ├─ count 不在 [1, 1000] → BAD_REQUEST
   └─ pages = ceil(count / 25)

4. 拿到中心点 location
   ├─ 传了 location → 直接用
   └─ 仅传 address → 调 v3 geocode
       ├─ geocodes 为空 → GEOCODE_NO_RESULT
       └─ 成功 → 取 first.location

5. 分页拉 v5 /place/around
   for page in range(1, pages+1):
     ├─ fetch 高德
     ├─ infocode == "10021" → 退避 1.5x 重试 ≤3 次
     ├─ infocode 在 INFOCODE_MAP → 立即抛对应 ErrorCode
     ├─ infocode 其他非 "1"/"10000" 值 → AMAP_OTHER_ERROR
     ├─ 累积 pois
     ├─ pois.length < page_size → break（无更多数据）
     └─ if page < pages: sleep(pages > 20 ? 100ms : 500ms)

6. 后处理
   ├─ normalizePoi 字段拍平（business.rating → 顶层 rating）
   ├─ 按 poi.id 去重，fallback name|location|address
   ├─ 按 distance_m 升序，name 中文 locale 二级排序
   └─ 算 nearest_10 + category_top_15

7. 返回 {ok: true, request_id, data: {...}}
```

### 高德请求 URL 模板

**Geocode (v3):**
```
GET https://restapi.amap.com/v3/geocode/geo
  ?key=<AMAP_WEB_SERVICE_KEY>
  &address=<address>
  &city=<city?>
  &output=JSON
```

**Nearby search (v5):**
```
GET https://restapi.amap.com/v5/place/around
  ?key=<AMAP_WEB_SERVICE_KEY>
  &location=<lng,lat>
  &radius=<radius>
  &page_size=25
  &page_num=<n>
  &show_fields=business
  &keywords=<keywords?>
  &types=<types?>
```

## 错误处理边界

| # | 出错位置 | 错误现象 | 捕获方 | 转换后 |
|---|---|---|---|---|
| 1 | LLM 输入 | 没填 address 也没 location | Tool execute() 第 ① 步 | ToolResult.fail("地址或经纬度至少要给一个") |
| 2 | Tool 端 | `amap_worker_url` 未配置 | Tool execute() 第 ② 步 | ToolResult.fail("amap_worker_url 未配置") |
| 3 | Tool 端 | `AMAP_WORKER_SECRET` 未配置 | Tool execute() 第 ③ 步 | ToolResult.fail("AMAP_WORKER_SECRET 未配置") |
| 4 | 网络 | 连不上 Cloudflare Worker | requests.ConnectionError | "无法连接 amap 服务器" |
| 5 | 网络 | Worker 慢/挂 | requests.Timeout | "amap 服务器响应超时" |
| 6 | Worker | Bearer Token 不匹配 | auth middleware | HTTP 401 + UNAUTHORIZED |
| 7 | Worker | handler 抛异常 | 顶层 error handler | HTTP 500 + INTERNAL_ERROR + request_id |
| 8 | Worker | AMAP_WEB_SERVICE_KEY secret 未设置 | 启动时 / 运行时 | HTTP 500 + INTERNAL_ERROR |
| 9 | Worker | geocode 找不到 | geocode service | HTTP 200 + GEOCODE_NO_RESULT |
| 10 | 高德 | 10021 重试耗尽 | fetchWithRetry | HTTP 200 + AMAP_QPS_EXCEEDED |
| 11 | 高德 | 10001/10009 key 失效 | fetchWithRetry | HTTP 200 + AMAP_KEY_INVALID |
| 12 | 高德 | 10003/10004 配额用尽 | fetchWithRetry | HTTP 200 + AMAP_QUOTA_EXCEEDED |
| 13 | 高德 | 非 JSON 响应/网络错误 | fetch catch | HTTP 504 + UPSTREAM_TIMEOUT |
| 14 | Worker | radius/count 越界 | 入参校验 | HTTP 400 + BAD_REQUEST |

**致命兜底**：Hono app 必须有全局 `onError` handler，转 500 + INTERNAL_ERROR + request_id，绝不允许裸 stack trace 泄漏。

## 测试策略

### 测试矩阵

| 层 | 测试类型 | 框架 | 覆盖目标 |
|---|---|---|---|
| Worker | 单元测试 | vitest + miniflare | geocode、around、normalize、auth |
| Tool 端 | 单元测试 | pytest + unittest.mock | execute() 各分支 |
| 端到端 | 手工 curl | bash | 部署后验证 |

### Worker 单测（`worker/amap/tests/`）

- `test_auth_missing_token` — 返回 401
- `test_auth_wrong_token` — 返回 401
- `test_missing_address_and_location` — 返回 400 BAD_REQUEST
- `test_geocode_happy` — mock fetch 返回正常 geocode 结果
- `test_geocode_no_result` — geocodes=[] 返回 GEOCODE_NO_RESULT
- `test_around_pagination` — 3 页响应合并
- `test_retry_on_10021` — 第一次 10021、第二次 ok
- `test_no_retry_on_10001` — key 失效立即抛错
- `test_normalize_business_flat` — business.rating → 顶层 rating
- `test_dedupe_by_id`
- `test_sort_by_distance`
- `test_summary_nearest_10`
- `test_summary_category_top_15`

### Tool 端单测（`tests/agent/tools/test_amap_nearby_poi.py`）

- `test_missing_address_and_location` — 触发 fail
- `test_missing_amap_worker_url` — 触发 fail
- `test_missing_amap_worker_secret` — 触发 fail
- `test_happy_path` — mock POST 返回 ok:true
- `test_worker_returns_401` — 翻译成"鉴权失败"
- `test_worker_returns_business_error_qps` — 翻译成"高德繁忙"
- `test_worker_timeout` — 翻译成"超时"
- `test_auth_header_sent` — 校验 outbound 请求带 Authorization: Bearer
- `test_device_code_header_sent` — 校验 outbound 请求带 X-Device-Code

### 端到端手工验证（部署后跑一次）

```bash
# 1. 无 auth → 401
curl -X POST https://metaclaw-amap.xxx.workers.dev/api/amap/nearby_poi \
  -H "Content-Type: application/json" -d '{}'
# 期望：401 UNAUTHORIZED

# 2. 缺参数 → 400
curl -X POST https://metaclaw-amap.xxx.workers.dev/api/amap/nearby_poi \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <secret>" \
  -d '{}'
# 期望：{"ok":false,"error":{"code":"BAD_REQUEST"...}}

# 3. 完整请求
curl -X POST https://metaclaw-amap.xxx.workers.dev/api/amap/nearby_poi \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <secret>" \
  -H "X-Device-Code: 0000000000000000000000000000abcd" \
  -d '{"address":"杭州未来研创园","city":"杭州","radius":3000}'
# 期望：{"ok":true,"data":{...}}

# 4. 客户端真打一次
# 在客户机器对话："帮我查杭州未来研创园附近 3 公里的咖啡店"
# 期望：LLM 自动调 amap_nearby_poi 返回若干咖啡店
```

## 部署流程

### Cloudflare Worker 部署

```bash
cd worker/amap

# 1. 安装依赖
npm install

# 2. 设置 secrets（交互式，只需一次）
npx wrangler secret put AMAP_WEB_SERVICE_KEY
npx wrangler secret put WORKER_AUTH_SECRET

# 3. 部署
npx wrangler deploy

# 部署完成后输出类似：
# Published metaclaw-amap (xxx.workers.dev)
# 记下这个 URL
```

### 阿里云中央 MetaClaw 配置

```bash
# .env 或 systemd unit 加：
AMAP_WORKER_URL=https://metaclaw-amap.xxx.workers.dev
AMAP_WORKER_SECRET=<跟 Cloudflare Worker 里 WORKER_AUTH_SECRET 相同的值>
```

### 高德 Key 获取流程（一次性）

1. [https://lbs.amap.com](https://lbs.amap.com) 注册账号 + 实名认证
2. 控制台 → 应用管理 → 创建新应用 `metaclaw-amap-proxy` → 类型选"通用"
3. 应用下"添加 Key" → **服务平台必须选"Web 服务"**（不是 Web 端 JS API）
4. 拿到 32 位字符串 → 通过 `wrangler secret put AMAP_WEB_SERVICE_KEY` 写入 Worker
5. **不要** 配 IP 白名单（Cloudflare Worker 出口 IP 不固定）

**已知配额**：免费个人 key 默认 100万次/天 + 50 QPS；企业 key 可申请提升。

## 设计决策记录

### 为什么用 Cloudflare Worker 而不是阿里云 Python endpoint

1. **Key 隔离**：高德 API key 存在 Cloudflare Worker Secrets（加密存储），阿里云中央服务器完全不持有 key，即使阿里云被入侵也不会泄露高德 key
2. **独立扩缩**：Worker 自动全球边缘部署，无需管理服务器，高德 QPS 压力不影响 MetaClaw 主进程
3. **技术栈适配**：Cloudflare Worker 原生 JS/TS 运行时，fetch API 天然适合做 HTTP 代理转发
4. **单仓库管理**：代码放 `worker/amap/` 子目录，git 一起走，不存在"另起一套独立基础设施"的维护负担

### 为什么选 Hono 而不是裸 fetch handler

Hono 是 Cloudflare Worker 生态最流行的轻量路由框架（~14KB），提供：中间件链（auth）、类型安全的 context、自动 JSON 解析、全局 error handler。比裸写 `addEventListener('fetch', ...)` 好维护，且几乎零性能开销。

### 为什么阿里云中央做中间层而不是客户直连 Worker

1. 复用现有 cloud_mode 链路：客户 → 阿里云中央的 X-Device-Code 鉴权 + per-device 计数已经跑通
2. 客户永远不需要知道 Cloudflare Worker 的存在（零配置）
3. Bearer Token secret 只在阿里云中央，不暴露给客户端
4. 未来加 kimi/天气等 worker 时，客户侧零改动

### 为什么客户侧零改动

客户侧 MetaClaw 在 cloud_mode 下只是透传代理，LLM 和 tools 都在阿里云中央跑。amap tool 的 `AMAP_WORKER_URL` 和 `AMAP_WORKER_SECRET` 只需要配在中央服务器上。客户装完 `--cloud-server-url` 即用，完全不知道 Cloudflare Worker 的存在。

### 为什么对外只暴露 `nearby_poi` 一个 action 但内部串接 geocode + around

棉花糖那份 mjs 已经验证过：用户给地名时内部偷偷跑一次 geocode 转坐标。让 LLM 反过来"先调 geocode tool 再调 around tool"会让一次自然语言提问在 LLM-tool 间往返多次，token 消耗 + 延迟都翻倍。Worker 端封装 = 客户端零思考。

### 为什么 nearest_10 + category_top_15 在 Worker 端算

聚合算 1 次（Worker）vs 算 N 次（每个客户每次都算）—— 显然前者更划算。LLM 拿到完整 200 条会浪费上下文 token，预聚合的 nearest_10 通常已经够 LLM 给出"附近商家有这些"这类回答。

## 第一版后的演进路径

按优先级（不在本 spec 范围）：

1. **观测**：扫 `api_counts.json` 找异常调用方，准备好黑名单切换钮
2. **缓存**：Cloudflare Cache API 对同坐标 + 半径 + keywords 30 分钟内复用结果
3. **白名单 / 黑名单**：Worker 端加 KV 存允许的 device code 列表
4. **更多高德能力**：路径规划 / 天气 / 文本搜索 POI（同一个 Worker 加新路由）
5. **多租户**：按 device_code 配额隔离 + 计费（KV 存 tenant 信息）
6. **自定义域名**：绑定自有域名替代 workers.dev
7. **Cloudflare Access**：加 IP 白名单或 mTLS 进一步加固

## 落地清单（实施计划入口）

实施计划见 `docs/superpowers/plans/2026-05-14-amap-worker.md`（待 spec approve 后用 writing-plans skill 生成）。

预期主要变更点：

- 新增 `worker/amap/`（完整 Cloudflare Worker 项目，~10 文件）
- 新增 `metaclaw/agent/tools/amap/`（2 文件）
- 修改 `metaclaw/agent/tools/__init__.py`（追加 import 和 __all__）
- 修改 `metaclaw/config/channel.py`（默认值 `amap_worker_url`）
- 新增测试 `worker/amap/tests/`、`tests/agent/tools/test_amap_nearby_poi.py`
- 阿里云中央 env 加 `AMAP_WORKER_URL` + `AMAP_WORKER_SECRET`（部署运维步骤）
- Cloudflare Worker secrets 加 `AMAP_WEB_SERVICE_KEY` + `WORKER_AUTH_SECRET`（wrangler secret put）

预计代码总量：~800-1000 行（含 Worker TS + Python Tool + 测试）。

## 附录：参考资料

- 棉花糖原版 codex skill：`/Users/coderhyh/Downloads/amap-nearby-poi/`（关键算法来源）
- MetaClaw cloud proxy 设计：`docs/superpowers/specs/2026-05-13-cloud-client-proxy-design.md`
- 高德 Web 服务 API：[https://lbs.amap.com/api/webservice/summary](https://lbs.amap.com/api/webservice/summary)
- 高德 v5 周边搜索：[https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch](https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch)
- Hono 框架：[https://hono.dev](https://hono.dev)
- Cloudflare Workers 文档：[https://developers.cloudflare.com/workers](https://developers.cloudflare.com/workers)
