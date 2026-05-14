# AMap Cloudflare Worker 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 Cloudflare Worker（TS + Hono）处理高德周边 POI 查询，并在 MetaClaw 中注册对应的 LLM Tool，实现三层调用链：客户 → 阿里云中央 → Cloudflare Worker → 高德 API。

**Architecture:** Cloudflare Worker 持有高德 API key，暴露 `POST /api/amap/nearby_poi`，内部串接 geocode + around。阿里云中央 MetaClaw 的 `AmapNearbyPoi` tool 通过 Bearer Token 鉴权调用 Worker。客户侧 cloud_mode 透传，零感知。

**Tech Stack:** TypeScript, Hono, Cloudflare Workers (wrangler), vitest + miniflare, Python (MetaClaw tool), pytest

---

## File Structure

### New Files

```
worker/amap/
├── package.json
├── tsconfig.json
├── wrangler.toml
├── vitest.config.ts
├── src/
│   ├── index.ts              # Hono app 入口
│   ├── types.ts              # 请求/响应/Bindings 类型
│   ├── errors.ts             # AmapError + ErrorCode + INFOCODE_MAP
│   ├── middleware/
│   │   └── auth.ts           # Bearer Token 校验
│   ├── routes/
│   │   └── nearby-poi.ts     # POST /api/amap/nearby_poi handler
│   └── services/
│       ├── geocode.ts        # 高德 v3 geocode
│       ├── around.ts         # 高德 v5 /place/around 分页+重试
│       └── normalize.ts      # POI 拍平 + 去重 + 排序 + summary
└── tests/
    ├── auth.test.ts
    ├── geocode.test.ts
    ├── around.test.ts
    ├── normalize.test.ts
    └── nearby-poi.test.ts

metaclaw/agent/tools/amap/
├── __init__.py
└── amap_nearby_poi.py

tests/agent/tools/
└── test_amap_nearby_poi.py
```

### Modified Files

```
metaclaw/agent/tools/__init__.py        # 追加 AmapNearbyPoi import + __all__
metaclaw/config/channel.py              # 追加 amap_worker_url 默认值
```

---

## Task 1: Worker 项目脚手架

**Files:**
- Create: `worker/amap/package.json`
- Create: `worker/amap/tsconfig.json`
- Create: `worker/amap/wrangler.toml`
- Create: `worker/amap/vitest.config.ts`
- Create: `worker/amap/src/types.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "metaclaw-amap-worker",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "hono": "^4.4.0"
  },
  "devDependencies": {
    "@cloudflare/vitest-pool-workers": "^0.5.0",
    "@cloudflare/workers-types": "^4.20240620.0",
    "typescript": "^5.5.0",
    "vitest": "^2.0.0",
    "wrangler": "^3.60.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "skipLibCheck": true,
    "lib": ["ES2022"],
    "types": ["@cloudflare/workers-types", "@cloudflare/vitest-pool-workers"],
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src/**/*.ts", "tests/**/*.ts"]
}
```

- [ ] **Step 3: Create wrangler.toml**

```toml
name = "metaclaw-amap"
main = "src/index.ts"
compatibility_date = "2024-06-01"
compatibility_flags = ["nodejs_compat"]

[vars]
ENVIRONMENT = "production"

# Secrets (set via `wrangler secret put`):
# AMAP_WEB_SERVICE_KEY - 高德 Web 服务 key
# WORKER_AUTH_SECRET   - Bearer Token 共享密钥
```

- [ ] **Step 4: Create vitest.config.ts**

```typescript
import { defineWorkersConfig } from '@cloudflare/vitest-pool-workers/config'

export default defineWorkersConfig({
  test: {
    poolOptions: {
      workers: {
        wrangler: { configPath: './wrangler.toml' },
      },
    },
  },
})
```

- [ ] **Step 5: Create src/types.ts**

```typescript
export type Bindings = {
  AMAP_WEB_SERVICE_KEY: string
  WORKER_AUTH_SECRET: string
  ENVIRONMENT: string
}

export interface NearbyPoiRequest {
  address?: string | null
  location?: string | null
  city?: string | null
  radius?: number
  keywords?: string | null
  types?: string | null
  count?: number
}

export interface Center {
  formatted_address: string
  location: string
  city: string
  district: string
}

export interface NormalizedPoi {
  id: string
  name: string
  category: string
  type: string
  typecode: string
  distance_m: number
  address: string
  province: string
  city: string
  district: string
  business_area: string
  rating: string
  cost: string
  tel: string
  open_time: string
  tag: string
  location: string
}

export interface PoiSummary {
  nearest_10: NormalizedPoi[]
  category_top_15: Array<{ category: string; count: number }>
}

export interface SuccessResponse {
  ok: true
  request_id: string
  data: {
    center: Center
    query: {
      radius_m: number
      keywords: string | null
      types: string | null
      count: number
    }
    unique_count: number
    rows: NormalizedPoi[]
    summary: PoiSummary
  }
}

export interface ErrorResponse {
  ok: false
  request_id: string
  error: {
    code: string
    message: string
    retryable: boolean
    details?: Record<string, unknown>
  }
}
```

- [ ] **Step 6: Install dependencies**

Run: `cd worker/amap && npm install`
Expected: `node_modules/` created, no errors

- [ ] **Step 7: Verify TypeScript compiles**

Run: `cd worker/amap && npx tsc --noEmit --pretty`
Expected: No errors (types.ts has no imports that need resolution yet)

---

## Task 2: Worker errors 模块

**Files:**
- Create: `worker/amap/src/errors.ts`

- [ ] **Step 1: Create src/errors.ts**

```typescript
export const ErrorCode = {
  UNAUTHORIZED: 'UNAUTHORIZED',
  BAD_REQUEST: 'BAD_REQUEST',
  GEOCODE_NO_RESULT: 'GEOCODE_NO_RESULT',
  AMAP_QPS_EXCEEDED: 'AMAP_QPS_EXCEEDED',
  AMAP_QUOTA_EXCEEDED: 'AMAP_QUOTA_EXCEEDED',
  AMAP_KEY_INVALID: 'AMAP_KEY_INVALID',
  AMAP_OTHER_ERROR: 'AMAP_OTHER_ERROR',
  UPSTREAM_TIMEOUT: 'UPSTREAM_TIMEOUT',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
} as const

export type ErrorCodeType = typeof ErrorCode[keyof typeof ErrorCode]

export const INFOCODE_MAP: Record<string, ErrorCodeType> = {
  '10001': ErrorCode.AMAP_KEY_INVALID,
  '10009': ErrorCode.AMAP_KEY_INVALID,
  '10003': ErrorCode.AMAP_QUOTA_EXCEEDED,
  '10004': ErrorCode.AMAP_QUOTA_EXCEEDED,
  '10021': ErrorCode.AMAP_QPS_EXCEEDED,
}

export class AmapError extends Error {
  constructor(
    public readonly code: ErrorCodeType,
    message: string,
    public readonly retryable: boolean = false,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message)
    this.name = 'AmapError'
  }
}
```

- [ ] **Step 2: Verify compilation**

Run: `cd worker/amap && npx tsc --noEmit --pretty`
Expected: No errors

---

## Task 3: Worker auth 中间件

**Files:**
- Create: `worker/amap/src/middleware/auth.ts`
- Create: `worker/amap/tests/auth.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// tests/auth.test.ts
import { env, createExecutionContext, waitOnExecutionContext } from 'cloudflare:test'
import { describe, it, expect } from 'vitest'
import app from '../src/index'

describe('auth middleware', () => {
  it('returns 401 when no Authorization header', async () => {
    const req = new Request('http://localhost/api/amap/nearby_poi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address: '杭州' }),
    })
    const ctx = createExecutionContext()
    const res = await app.fetch(req, env, ctx)
    await waitOnExecutionContext(ctx)
    expect(res.status).toBe(401)
    const body = await res.json() as any
    expect(body.ok).toBe(false)
    expect(body.error.code).toBe('UNAUTHORIZED')
  })

  it('returns 401 when token is wrong', async () => {
    const req = new Request('http://localhost/api/amap/nearby_poi', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer wrong-token',
      },
      body: JSON.stringify({ address: '杭州' }),
    })
    const ctx = createExecutionContext()
    const res = await app.fetch(req, env, ctx)
    await waitOnExecutionContext(ctx)
    expect(res.status).toBe(401)
  })

  it('passes when token is correct', async () => {
    const req = new Request('http://localhost/api/amap/nearby_poi', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.WORKER_AUTH_SECRET}`,
      },
      body: JSON.stringify({ address: '杭州', city: '杭州' }),
    })
    const ctx = createExecutionContext()
    const res = await app.fetch(req, env, ctx)
    await waitOnExecutionContext(ctx)
    // Should not be 401 (might be other error since geocode isn't mocked)
    expect(res.status).not.toBe(401)
  })
})
```

- [ ] **Step 2: Create src/middleware/auth.ts**

```typescript
import type { Context, Next } from 'hono'
import type { Bindings } from '../types'

export async function authMiddleware(c: Context<{ Bindings: Bindings }>, next: Next) {
  const authHeader = c.req.header('Authorization') || ''
  const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : ''

  if (!token || token !== c.env.WORKER_AUTH_SECRET) {
    return c.json(
      {
        ok: false,
        request_id: crypto.randomUUID(),
        error: {
          code: 'UNAUTHORIZED',
          message: 'Invalid or missing auth token',
          retryable: false,
        },
      },
      401,
    )
  }

  await next()
}
```

- [ ] **Step 3: Create minimal src/index.ts to make tests compile**

```typescript
import { Hono } from 'hono'
import type { Bindings } from './types'
import { authMiddleware } from './middleware/auth'

const app = new Hono<{ Bindings: Bindings }>()

app.use('/api/*', authMiddleware)

app.post('/api/amap/nearby_poi', async (c) => {
  return c.json({ ok: false, request_id: '', error: { code: 'NOT_IMPLEMENTED', message: 'TODO', retryable: false } }, 500)
})

export default app
```

- [ ] **Step 4: Add test env vars to wrangler.toml**

Append to `wrangler.toml`:

```toml
[vars]
ENVIRONMENT = "production"
WORKER_AUTH_SECRET = "test-secret-for-dev"
AMAP_WEB_SERVICE_KEY = "test-amap-key"
```

- [ ] **Step 5: Run tests**

Run: `cd worker/amap && npx vitest run tests/auth.test.ts`
Expected: All 3 tests PASS

---

## Task 4: Worker normalize 服务

**Files:**
- Create: `worker/amap/src/services/normalize.ts`
- Create: `worker/amap/tests/normalize.test.ts`

- [ ] **Step 1: Write the failing tests**

```typescript
// tests/normalize.test.ts
import { describe, it, expect } from 'vitest'
import { normalizePoi, dedupe, sortByDistance, buildSummary } from '../src/services/normalize'

describe('normalizePoi', () => {
  it('flattens business fields to top level', () => {
    const raw = {
      id: 'B001',
      name: '星巴克',
      type: '餐饮服务;咖啡厅',
      typecode: '050500',
      distance: '142',
      address: '某路1号',
      pname: '浙江省',
      cityname: '杭州市',
      adname: '余杭区',
      location: '120.03,30.24',
      business: {
        keytag: '咖啡厅',
        business_area: '仓前',
        rating: '4.6',
        cost: '35',
        tel: '0571-88888888',
        opentime_week: '周一至周日 07:00-22:00',
        tag: '美式咖啡;拿铁',
      },
    }
    const result = normalizePoi(raw)
    expect(result.id).toBe('B001')
    expect(result.name).toBe('星巴克')
    expect(result.category).toBe('咖啡厅')
    expect(result.distance_m).toBe(142)
    expect(result.rating).toBe('4.6')
    expect(result.cost).toBe('35')
    expect(result.tel).toBe('0571-88888888')
    expect(result.open_time).toBe('周一至周日 07:00-22:00')
    expect(result.business_area).toBe('仓前')
  })

  it('handles missing business object', () => {
    const raw = { id: 'B002', name: '小店', distance: '500', location: '120,30' }
    const result = normalizePoi(raw)
    expect(result.rating).toBe('')
    expect(result.category).toBe('')
  })
})

describe('dedupe', () => {
  it('removes duplicates by id', () => {
    const rows = [
      { id: 'A', name: 'X', distance_m: 100, location: '1,2', address: 'a' },
      { id: 'A', name: 'X', distance_m: 100, location: '1,2', address: 'a' },
      { id: 'B', name: 'Y', distance_m: 200, location: '3,4', address: 'b' },
    ] as any
    expect(dedupe(rows)).toHaveLength(2)
  })

  it('dedupes by name|location|address when id is empty', () => {
    const rows = [
      { id: '', name: 'X', distance_m: 100, location: '1,2', address: 'a' },
      { id: '', name: 'X', distance_m: 100, location: '1,2', address: 'a' },
    ] as any
    expect(dedupe(rows)).toHaveLength(1)
  })
})

describe('sortByDistance', () => {
  it('sorts ascending by distance_m', () => {
    const rows = [
      { distance_m: 300, name: 'C' },
      { distance_m: 100, name: 'A' },
      { distance_m: 200, name: 'B' },
    ] as any
    const sorted = sortByDistance(rows)
    expect(sorted[0].distance_m).toBe(100)
    expect(sorted[1].distance_m).toBe(200)
    expect(sorted[2].distance_m).toBe(300)
  })
})

describe('buildSummary', () => {
  it('returns nearest_10 and category_top_15', () => {
    const rows = Array.from({ length: 20 }, (_, i) => ({
      distance_m: (i + 1) * 100,
      name: `POI${i}`,
      category: i < 10 ? '中餐厅' : '快餐厅',
    })) as any
    const summary = buildSummary(rows)
    expect(summary.nearest_10).toHaveLength(10)
    expect(summary.nearest_10[0].distance_m).toBe(100)
    expect(summary.category_top_15.length).toBeGreaterThan(0)
    expect(summary.category_top_15[0].category).toBe('中餐厅')
    expect(summary.category_top_15[0].count).toBe(10)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd worker/amap && npx vitest run tests/normalize.test.ts`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement src/services/normalize.ts**

```typescript
import type { NormalizedPoi, PoiSummary } from '../types'

export function normalizePoi(raw: Record<string, any>): NormalizedPoi {
  const business = raw.business || {}
  return {
    id: raw.id || '',
    name: raw.name || '',
    category: business.keytag || raw.type || '',
    type: raw.type || '',
    typecode: raw.typecode || '',
    distance_m: Number(raw.distance || 0),
    address: raw.address || '',
    province: raw.pname || '',
    city: raw.cityname || '',
    district: raw.adname || '',
    business_area: business.business_area || '',
    rating: business.rating || '',
    cost: business.cost || '',
    tel: business.tel || '',
    open_time: business.opentime_week || business.opentime_today || '',
    tag: business.tag || '',
    location: raw.location || '',
  }
}

export function dedupe(rows: NormalizedPoi[]): NormalizedPoi[] {
  const seen = new Set<string>()
  return rows.filter((row) => {
    const key = row.id || `${row.name}|${row.location}|${row.address}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function sortByDistance(rows: NormalizedPoi[]): NormalizedPoi[] {
  return [...rows].sort((a, b) => a.distance_m - b.distance_m || a.name.localeCompare(b.name, 'zh-CN'))
}

export function buildSummary(rows: NormalizedPoi[]): PoiSummary {
  const nearest_10 = rows.slice(0, 10)

  const categoryCount = new Map<string, number>()
  for (const row of rows) {
    if (row.category) {
      categoryCount.set(row.category, (categoryCount.get(row.category) || 0) + 1)
    }
  }
  const category_top_15 = [...categoryCount.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([category, count]) => ({ category, count }))

  return { nearest_10, category_top_15 }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd worker/amap && npx vitest run tests/normalize.test.ts`
Expected: All tests PASS

---

## Task 5: Worker geocode 服务

**Files:**
- Create: `worker/amap/src/services/geocode.ts`
- Create: `worker/amap/tests/geocode.test.ts`

- [ ] **Step 1: Write the failing tests**

```typescript
// tests/geocode.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { geocode } from '../src/services/geocode'

// Mock global fetch
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

describe('geocode', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('returns center on success', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: '1',
        infocode: '10000',
        geocodes: [{
          formatted_address: '浙江省杭州市余杭区未来研创园',
          location: '120.037925,30.245525',
          city: '杭州市',
          district: '余杭区',
        }],
      }),
    })

    const result = await geocode('未来研创园', '杭州', 'test-key')
    expect(result.location).toBe('120.037925,30.245525')
    expect(result.formatted_address).toContain('未来研创园')
  })

  it('throws GEOCODE_NO_RESULT when geocodes is empty', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: '1',
        infocode: '10000',
        geocodes: [],
      }),
    })

    await expect(geocode('不存在的地方xyz', null, 'test-key'))
      .rejects.toThrow('GEOCODE_NO_RESULT')
  })

  it('throws AMAP_KEY_INVALID on infocode 10001', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: '0',
        infocode: '10001',
        info: 'INVALID_USER_KEY',
      }),
    })

    await expect(geocode('杭州', null, 'bad-key'))
      .rejects.toThrow('AMAP_KEY_INVALID')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd worker/amap && npx vitest run tests/geocode.test.ts`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement src/services/geocode.ts**

```typescript
import type { Center } from '../types'
import { AmapError, ErrorCode, INFOCODE_MAP } from '../errors'

const GEOCODE_URL = 'https://restapi.amap.com/v3/geocode/geo'

export async function geocode(address: string, city: string | null, key: string): Promise<Center> {
  const params = new URLSearchParams({
    key,
    address,
    output: 'JSON',
  })
  if (city) params.set('city', city)

  const resp = await fetch(`${GEOCODE_URL}?${params}`)
  if (!resp.ok) {
    throw new AmapError(ErrorCode.UPSTREAM_TIMEOUT, `高德 geocode HTTP ${resp.status}`, true)
  }

  const data = await resp.json() as Record<string, any>

  if (data.infocode && data.infocode !== '10000' && data.infocode !== '1') {
    const mapped = INFOCODE_MAP[data.infocode]
    if (mapped) {
      throw new AmapError(mapped, data.info || '高德 geocode 错误', mapped === ErrorCode.AMAP_QPS_EXCEEDED)
    }
    throw new AmapError(ErrorCode.AMAP_OTHER_ERROR, `高德 geocode: ${data.info || data.infocode}`)
  }

  const geocodes = data.geocodes || []
  if (geocodes.length === 0) {
    throw new AmapError(ErrorCode.GEOCODE_NO_RESULT, `找不到地址: ${address}`)
  }

  const first = geocodes[0]
  return {
    formatted_address: first.formatted_address || address,
    location: first.location,
    city: first.city || city || '',
    district: first.district || '',
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd worker/amap && npx vitest run tests/geocode.test.ts`
Expected: All 3 tests PASS

---

## Task 6: Worker around 服务

**Files:**
- Create: `worker/amap/src/services/around.ts`
- Create: `worker/amap/tests/around.test.ts`

- [ ] **Step 1: Write the failing tests**

```typescript
// tests/around.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { queryAround } from '../src/services/around'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function makePage(count: number, startId: number = 1) {
  return {
    status: '1',
    infocode: '10000',
    pois: Array.from({ length: count }, (_, i) => ({
      id: `B${String(startId + i).padStart(4, '0')}`,
      name: `POI${startId + i}`,
      distance: String((startId + i) * 100),
      location: '120.03,30.24',
    })),
  }
}

describe('queryAround', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('fetches multiple pages and merges results', async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => makePage(25, 1) })
      .mockResolvedValueOnce({ ok: true, json: async () => makePage(25, 26) })
      .mockResolvedValueOnce({ ok: true, json: async () => makePage(10, 51) })

    const result = await queryAround({
      key: 'test-key',
      location: '120.03,30.24',
      radius: 3000,
      targetCount: 60,
      keywords: null,
      types: null,
    })

    expect(result).toHaveLength(60)
  })

  it('stops early when page returns fewer than page_size', async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => makePage(25, 1) })
      .mockResolvedValueOnce({ ok: true, json: async () => makePage(5, 26) })

    const result = await queryAround({
      key: 'test-key',
      location: '120.03,30.24',
      radius: 3000,
      targetCount: 200,
      keywords: null,
      types: null,
    })

    expect(result).toHaveLength(30)
    expect(mockFetch).toHaveBeenCalledTimes(2)
  })

  it('retries on infocode 10021 with backoff', async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: '0', infocode: '10021', info: 'QPS_LIMIT' }) })
      .mockResolvedValueOnce({ ok: true, json: async () => makePage(10, 1) })

    const result = await queryAround({
      key: 'test-key',
      location: '120.03,30.24',
      radius: 3000,
      targetCount: 10,
      keywords: null,
      types: null,
    })

    expect(result).toHaveLength(10)
    expect(mockFetch).toHaveBeenCalledTimes(2)
  })

  it('throws immediately on infocode 10001', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: '0', infocode: '10001', info: 'INVALID_USER_KEY' }),
    })

    await expect(queryAround({
      key: 'bad-key',
      location: '120.03,30.24',
      radius: 3000,
      targetCount: 10,
      keywords: null,
      types: null,
    })).rejects.toThrow('AMAP_KEY_INVALID')
  })

  it('includes show_fields=business and correct params', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => makePage(5, 1) })

    await queryAround({
      key: 'test-key',
      location: '120.03,30.24',
      radius: 5000,
      targetCount: 5,
      keywords: '咖啡',
      types: null,
    })

    const calledUrl = mockFetch.mock.calls[0][0] as string
    expect(calledUrl).toContain('show_fields=business')
    expect(calledUrl).toContain('page_size=25')
    expect(calledUrl).toContain('radius=5000')
    expect(calledUrl).toContain('keywords=' + encodeURIComponent('咖啡'))
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd worker/amap && npx vitest run tests/around.test.ts`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement src/services/around.ts**

```typescript
import { AmapError, ErrorCode, INFOCODE_MAP } from '../errors'

const AROUND_URL = 'https://restapi.amap.com/v5/place/around'
const PAGE_SIZE = 25

export interface AroundOptions {
  key: string
  location: string
  radius: number
  targetCount: number
  keywords: string | null
  types: string | null
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function fetchWithRetry(url: string, retries = 3, delayMs = 1200): Promise<Record<string, any>> {
  for (let i = 0; i <= retries; i++) {
    const resp = await fetch(url)
    if (!resp.ok) {
      throw new AmapError(ErrorCode.UPSTREAM_TIMEOUT, `高德 around HTTP ${resp.status}`, true)
    }

    const data = await resp.json() as Record<string, any>

    if (data.infocode === '10021') {
      if (i === retries) {
        throw new AmapError(ErrorCode.AMAP_QPS_EXCEEDED, '高德接口限流，重试耗尽', true, { infocode: '10021' })
      }
      await sleep(delayMs * Math.pow(1.5, i))
      continue
    }

    const mapped = INFOCODE_MAP[data.infocode]
    if (mapped && mapped !== ErrorCode.AMAP_QPS_EXCEEDED) {
      throw new AmapError(mapped, data.info || '高德返回错误', false, { infocode: data.infocode })
    }

    if (data.infocode !== '1' && data.infocode !== '10000') {
      throw new AmapError(ErrorCode.AMAP_OTHER_ERROR, `高德返回: ${data.info || data.infocode}`, false)
    }

    return data
  }

  throw new AmapError(ErrorCode.AMAP_QPS_EXCEEDED, '高德接口限流', true)
}

export async function queryAround(opts: AroundOptions): Promise<Record<string, any>[]> {
  const pages = Math.ceil(opts.targetCount / PAGE_SIZE)
  const allPois: Record<string, any>[] = []

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

    const data = await fetchWithRetry(`${AROUND_URL}?${params}`)
    const pois = data.pois || []
    allPois.push(...pois)

    if (pois.length < PAGE_SIZE) break
    if (page < pages) {
      await sleep(pages > 20 ? 100 : 500)
    }
  }

  return allPois
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd worker/amap && npx vitest run tests/around.test.ts`
Expected: All 5 tests PASS

---

## Task 7: Worker nearby-poi 路由（集成）

**Files:**
- Create: `worker/amap/src/routes/nearby-poi.ts`
- Modify: `worker/amap/src/index.ts`
- Create: `worker/amap/tests/nearby-poi.test.ts`

- [ ] **Step 1: Write the integration test**

```typescript
// tests/nearby-poi.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { env, createExecutionContext, waitOnExecutionContext } from 'cloudflare:test'
import app from '../src/index'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function makeGeocodeResponse() {
  return {
    ok: true,
    json: async () => ({
      status: '1',
      infocode: '10000',
      geocodes: [{
        formatted_address: '浙江省杭州市余杭区未来研创园',
        location: '120.037925,30.245525',
        city: '杭州市',
        district: '余杭区',
      }],
    }),
  }
}

function makeAroundResponse(count: number) {
  return {
    ok: true,
    json: async () => ({
      status: '1',
      infocode: '10000',
      pois: Array.from({ length: count }, (_, i) => ({
        id: `B${String(i + 1).padStart(4, '0')}`,
        name: `商家${i + 1}`,
        type: '餐饮服务;中餐厅',
        typecode: '050100',
        distance: String((i + 1) * 50),
        address: `某路${i + 1}号`,
        pname: '浙江省',
        cityname: '杭州市',
        adname: '余杭区',
        location: `120.03${i},30.24${i}`,
        business: {
          keytag: '中餐厅',
          rating: '4.5',
          cost: '50',
          tel: '0571-88888888',
        },
      })),
    }),
  }
}

describe('POST /api/amap/nearby_poi', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('returns BAD_REQUEST when no address or location', async () => {
    const req = new Request('http://localhost/api/amap/nearby_poi', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.WORKER_AUTH_SECRET}`,
      },
      body: JSON.stringify({}),
    })
    const ctx = createExecutionContext()
    const res = await app.fetch(req, env, ctx)
    await waitOnExecutionContext(ctx)
    const body = await res.json() as any
    expect(body.ok).toBe(false)
    expect(body.error.code).toBe('BAD_REQUEST')
  })

  it('returns BAD_REQUEST when radius out of range', async () => {
    const req = new Request('http://localhost/api/amap/nearby_poi', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.WORKER_AUTH_SECRET}`,
      },
      body: JSON.stringify({ address: '杭州', radius: 100000 }),
    })
    const ctx = createExecutionContext()
    const res = await app.fetch(req, env, ctx)
    await waitOnExecutionContext(ctx)
    const body = await res.json() as any
    expect(body.ok).toBe(false)
    expect(body.error.code).toBe('BAD_REQUEST')
  })

  it('happy path with address: geocode + around + normalize', async () => {
    mockFetch
      .mockResolvedValueOnce(makeGeocodeResponse())
      .mockResolvedValueOnce(makeAroundResponse(10))

    const req = new Request('http://localhost/api/amap/nearby_poi', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.WORKER_AUTH_SECRET}`,
      },
      body: JSON.stringify({ address: '杭州未来研创园', city: '杭州', radius: 3000, count: 10 }),
    })
    const ctx = createExecutionContext()
    const res = await app.fetch(req, env, ctx)
    await waitOnExecutionContext(ctx)
    expect(res.status).toBe(200)
    const body = await res.json() as any
    expect(body.ok).toBe(true)
    expect(body.data.unique_count).toBe(10)
    expect(body.data.rows[0].name).toBe('商家1')
    expect(body.data.rows[0].rating).toBe('4.5')
    expect(body.data.summary.nearest_10).toHaveLength(10)
  })

  it('happy path with location: skips geocode', async () => {
    mockFetch.mockResolvedValueOnce(makeAroundResponse(5))

    const req = new Request('http://localhost/api/amap/nearby_poi', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.WORKER_AUTH_SECRET}`,
      },
      body: JSON.stringify({ location: '120.03,30.24', radius: 1000, count: 5 }),
    })
    const ctx = createExecutionContext()
    const res = await app.fetch(req, env, ctx)
    await waitOnExecutionContext(ctx)
    const body = await res.json() as any
    expect(body.ok).toBe(true)
    expect(mockFetch).toHaveBeenCalledTimes(1) // only around, no geocode
  })
})
```

- [ ] **Step 2: Implement src/routes/nearby-poi.ts**

```typescript
import type { Context } from 'hono'
import type { Bindings, NearbyPoiRequest } from '../types'
import { AmapError, ErrorCode } from '../errors'
import { geocode } from '../services/geocode'
import { queryAround } from '../services/around'
import { normalizePoi, dedupe, sortByDistance, buildSummary } from '../services/normalize'

interface ValidatedRequest {
  address: string | null
  location: string | null
  city: string | null
  radius: number
  keywords: string | null
  types: string | null
  count: number
}

function validateRequest(body: NearbyPoiRequest): ValidatedRequest {
  const address = body.address?.trim() || null
  const location = body.location?.trim() || null

  if (!address && !location) {
    throw new AmapError(ErrorCode.BAD_REQUEST, '地址或经纬度至少要给一个')
  }

  if (location && !/^-?\d+(\.\d+)?,-?\d+(\.\d+)?$/.test(location)) {
    throw new AmapError(ErrorCode.BAD_REQUEST, 'location 格式错误，应为 "lng,lat"')
  }

  const radius = body.radius ?? 3000
  if (radius < 1 || radius > 50000) {
    throw new AmapError(ErrorCode.BAD_REQUEST, 'radius 必须在 1-50000 之间')
  }

  const count = body.count ?? 200
  if (count < 1 || count > 1000) {
    throw new AmapError(ErrorCode.BAD_REQUEST, 'count 必须在 1-1000 之间')
  }

  return {
    address,
    location,
    city: body.city?.trim() || null,
    radius,
    keywords: body.keywords?.trim() || null,
    types: body.types?.trim() || null,
    count,
  }
}

export async function nearbyPoi(c: Context<{ Bindings: Bindings }>) {
  const requestId = crypto.randomUUID()

  try {
    const body = await c.req.json<NearbyPoiRequest>()
    const validated = validateRequest(body)

    let location = validated.location
    let center = null

    if (!location) {
      center = await geocode(validated.address!, validated.city, c.env.AMAP_WEB_SERVICE_KEY)
      location = center.location
    } else {
      center = { formatted_address: '', location, city: '', district: '' }
    }

    const rawPois = await queryAround({
      key: c.env.AMAP_WEB_SERVICE_KEY,
      location,
      radius: validated.radius,
      targetCount: validated.count,
      keywords: validated.keywords,
      types: validated.types,
    })

    const normalized = rawPois.map((p) => normalizePoi(p))
    const deduped = dedupe(normalized)
    const sorted = sortByDistance(deduped)
    const summary = buildSummary(sorted)

    return c.json({
      ok: true,
      request_id: requestId,
      data: {
        center,
        query: {
          radius_m: validated.radius,
          keywords: validated.keywords,
          types: validated.types,
          count: validated.count,
        },
        unique_count: sorted.length,
        rows: sorted,
        summary,
      },
    })
  } catch (err) {
    if (err instanceof AmapError) {
      const status = err.code === ErrorCode.BAD_REQUEST ? 400
        : err.code === ErrorCode.UPSTREAM_TIMEOUT ? 504
        : 200
      return c.json({
        ok: false,
        request_id: requestId,
        error: {
          code: err.code,
          message: err.message,
          retryable: err.retryable,
          details: err.details,
        },
      }, status)
    }

    return c.json({
      ok: false,
      request_id: requestId,
      error: {
        code: 'INTERNAL_ERROR',
        message: 'Worker 内部错误',
        retryable: false,
      },
    }, 500)
  }
}
```

- [ ] **Step 3: Update src/index.ts to use the real route**

```typescript
import { Hono } from 'hono'
import type { Bindings } from './types'
import { authMiddleware } from './middleware/auth'
import { nearbyPoi } from './routes/nearby-poi'

const app = new Hono<{ Bindings: Bindings }>()

app.use('/api/*', authMiddleware)
app.post('/api/amap/nearby_poi', nearbyPoi)

app.onError((err, c) => {
  return c.json({
    ok: false,
    request_id: crypto.randomUUID(),
    error: {
      code: 'INTERNAL_ERROR',
      message: 'Worker 内部错误',
      retryable: false,
    },
  }, 500)
})

export default app
```

- [ ] **Step 4: Run all Worker tests**

Run: `cd worker/amap && npx vitest run`
Expected: All tests PASS (auth + normalize + geocode + around + nearby-poi)

---

## Task 8: Python Tool — AmapNearbyPoi

**Files:**
- Create: `metaclaw/agent/tools/amap/__init__.py`
- Create: `metaclaw/agent/tools/amap/amap_nearby_poi.py`
- Create: `tests/agent/tools/test_amap_nearby_poi.py`

- [ ] **Step 1: Create metaclaw/agent/tools/amap/__init__.py**

```python
from agent.tools.amap.amap_nearby_poi import AmapNearbyPoi

__all__ = ["AmapNearbyPoi"]
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/agent/tools/test_amap_nearby_poi.py
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
                assert "AMAP_WORKER_URL" in result.result or "amap_worker_url" in result.result

    def test_missing_amap_worker_secret(self, tool):
        with patch.dict(os.environ, {"AMAP_WORKER_URL": "https://example.com"}, clear=True):
            with patch("agent.tools.amap.amap_nearby_poi.conf", return_value={"amap_worker_url": "https://example.com"}):
                result = tool.execute({"address": "杭州"})
                assert result.status == "error"
                assert "AMAP_WORKER_SECRET" in result.result


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
        assert "Authorization" in call_kwargs.kwargs["headers"]
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
        import requests as req_lib
        mock_post.side_effect = req_lib.Timeout("timeout")

        with patch.dict(os.environ, {
            "AMAP_WORKER_URL": "https://worker.example.com",
            "AMAP_WORKER_SECRET": "secret123",
        }):
            result = tool.execute({"address": "杭州"})

        assert result.status == "error"
        assert "超时" in result.result
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/coderhyh/Desktop/yuanhe/MetaClaw/metaclaw/metaclaw && python -m pytest tests/agent/tools/test_amap_nearby_poi.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement metaclaw/agent/tools/amap/amap_nearby_poi.py**

```python
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
            return ToolResult.fail("AMAP_WORKER_URL 未配置，无法使用高德周边搜索")

        worker_secret = os.environ.get("AMAP_WORKER_SECRET", "")
        if not worker_secret:
            return ToolResult.fail("AMAP_WORKER_SECRET 未配置，无法使用高德周边搜索")

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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/coderhyh/Desktop/yuanhe/MetaClaw/metaclaw/metaclaw && python -m pytest tests/agent/tools/test_amap_nearby_poi.py -v`
Expected: All tests PASS

---

## Task 9: 注册 Tool + 配置默认值

**Files:**
- Modify: `metaclaw/agent/tools/__init__.py`
- Modify: `metaclaw/config/channel.py`

- [ ] **Step 1: 修改 metaclaw/agent/tools/__init__.py**

在 `_import_optional_tools()` 函数内，`Vision` 那段之后追加：

```python
    # AmapNearbyPoi Tool
    try:
        from agent.tools.amap.amap_nearby_poi import AmapNearbyPoi
        tools['AmapNearbyPoi'] = AmapNearbyPoi
    except ImportError as e:
        logger.error(f"[Tools] AmapNearbyPoi not loaded - missing dependency: {e}")
    except Exception as e:
        logger.error(f"[Tools] AmapNearbyPoi failed to load: {e}")
```

在 `_optional_tools = _import_optional_tools()` 之后追加：

```python
AmapNearbyPoi = _optional_tools.get('AmapNearbyPoi')
```

在 `__all__` 列表追加：

```python
    'AmapNearbyPoi',
```

- [ ] **Step 2: 修改 metaclaw/config/channel.py**

在 `CHANNEL_SETTINGS` 字典中 `"cloud_server_url": ""` 那行之后追加：

```python
    "amap_worker_url": "",  # Cloudflare Worker 地址，留空则禁用 amap_nearby_poi tool
```

- [ ] **Step 3: 验证 import 不报错**

Run: `cd /Users/coderhyh/Desktop/yuanhe/MetaClaw/metaclaw/metaclaw && python -c "from agent.tools import AmapNearbyPoi; print(AmapNearbyPoi)"`
Expected: 输出 `<class 'agent.tools.amap.amap_nearby_poi.AmapNearbyPoi'>` 或 `None`（取决于 env 是否配了）

---

## Task 10: Cloudflare Worker 部署 + 端到端验证

**Files:** 无新文件，运维操作

- [ ] **Step 1: 生成共享密钥**

Run: `openssl rand -hex 32`
记下输出值作为 `WORKER_AUTH_SECRET`

- [ ] **Step 2: 部署 Worker 到 Cloudflare**

```bash
cd worker/amap
npx wrangler secret put AMAP_WEB_SERVICE_KEY
# 交互式输入高德 Web 服务 key

npx wrangler secret put WORKER_AUTH_SECRET
# 交互式输入 Step 1 生成的密钥

npx wrangler deploy
```

Expected: 输出 `Published metaclaw-amap (https://metaclaw-amap.xxx.workers.dev)`

- [ ] **Step 3: 配置阿里云中央 MetaClaw**

在阿里云服务器的 MetaClaw `.env` 或 systemd unit 中加：

```bash
AMAP_WORKER_URL=https://metaclaw-amap.xxx.workers.dev
AMAP_WORKER_SECRET=<Step 1 的密钥>
```

重启 MetaClaw 服务。

- [ ] **Step 4: 端到端验证 — 无 auth**

```bash
curl -X POST https://metaclaw-amap.xxx.workers.dev/api/amap/nearby_poi \
  -H "Content-Type: application/json" -d '{}'
```

Expected: HTTP 401, `{"ok":false,"error":{"code":"UNAUTHORIZED",...}}`

- [ ] **Step 5: 端到端验证 — 缺参数**

```bash
curl -X POST https://metaclaw-amap.xxx.workers.dev/api/amap/nearby_poi \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <secret>" \
  -d '{}'
```

Expected: HTTP 400, `{"ok":false,"error":{"code":"BAD_REQUEST",...}}`

- [ ] **Step 6: 端到端验证 — 完整请求**

```bash
curl -X POST https://metaclaw-amap.xxx.workers.dev/api/amap/nearby_poi \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <secret>" \
  -d '{"address":"杭州未来研创园","city":"杭州","radius":3000,"count":10}'
```

Expected: HTTP 200, `{"ok":true,"data":{"unique_count":...,"rows":[...],...}}`

- [ ] **Step 7: 端到端验证 — 客户端对话**

在客户机器对话："帮我查杭州未来研创园附近 3 公里的咖啡店"

Expected: LLM 自动调用 `amap_nearby_poi` tool，返回若干咖啡店信息

