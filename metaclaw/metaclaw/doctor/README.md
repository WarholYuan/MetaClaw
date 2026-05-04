# Metadoctor 使用说明

Metadoctor 是 MetaClaw 的 companion 守护进程，用于监控 MetaClaw 的运行健康状态，并通过飞书 IM 与用户交互式对话，让用户能够远程诊断和修复 MetaClaw 的问题。

## 功能概述

- **进程监控**：每 30 秒检查 MetaClaw 进程是否存活
- **日志活跃度检测**：检测 MetaClaw 是否卡住（长时间无日志输出）
- **内存监控**（可选）：检测内存使用是否过高（需要安装 `psutil`）
- **飞书告警**：状态变化时自动发送飞书通知
- **交互式修复**：通过飞书私聊发送命令远程控制 MetaClaw

## 前置条件

1. MetaClaw 已安装并正常运行
2. 已在飞书开放平台创建**独立的飞书应用**（不能与 MetaClaw 主应用共用）
3. 已安装 `lark-oapi`（MetaClaw 飞书 channel 已依赖，通常已安装）

```bash
pip install lark-oapi
```

## 飞书应用配置

### 1. 创建飞书应用

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 记录 **App ID** 和 **App Secret**
4. 进入「权限管理」，添加以下权限：
   - `im:message`（读取和发送消息）
   - `im:message.group`（群聊消息，如需要）
5. 进入「事件订阅」，添加事件：
   - `im.message.receive_v1`（接收消息 v2.0）
6. 选择 **使用长连接接收事件**（WebSocket 模式）
7. 发布应用并给自己添加可用范围

### 2. 获取 notify_open_id

Metadoctor 需要知道把告警发给哪个用户。获取你的 open_id：

1. 在飞书开放平台 → 应用首页，使用「在线调试」功能
2. 调用 `contact.v3.users.find_by_department` 或直接查看自己的用户信息
3. 记录下你的 `open_id`（格式如 `ou_xxxxxxxxxxxxxxxx`）

> 或者：先随意配置一个值启动 Metadoctor，给它发一条消息，查看日志中打印的 `open_id`。

## config.json 配置

在 `config.json` 中添加以下配置项：

```json
{
  "metadoctor_enabled": true,
  "metadoctor_feishu_app_id": "cli_xxxxxxxxxxxxxxxx",
  "metadoctor_feishu_app_secret": "your_app_secret_here",
  "metadoctor_notify_open_id": "ou_xxxxxxxxxxxxxxxx",
  "metadoctor_check_interval": 30,
  "metadoctor_auto_restart": false
}
```

### 配置项说明

| 配置项 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `metadoctor_enabled` | bool | 是 | `false` | 是否启用 Metadoctor |
| `metadoctor_feishu_app_id` | str | 是 | `""` | Metadoctor 专用飞书 App ID |
| `metadoctor_feishu_app_secret` | str | 是 | `""` | Metadoctor 专用飞书 App Secret |
| `metadoctor_notify_open_id` | str | 否 | `""` | 接收告警的飞书用户 open_id |
| `metadoctor_check_interval` | int | 否 | `30` | 健康检查间隔（秒） |
| `metadoctor_auto_restart` | bool | 否 | `false` | 是否自动重启（默认仅告警） |

## 启动与停止

### 启动 Metadoctor

```bash
metaclaw doctor start
```

后台启动守护进程，日志写入 `~/metaclaw/logs/metadoctor.log`。

前台启动（调试用）：

```bash
metaclaw doctor start --foreground
```

### 查看状态

```bash
metaclaw doctor status
```

### 查看日志

```bash
metaclaw doctor logs          # 最后 50 行
metaclaw doctor logs -f       # 实时跟踪
```

### 停止 Metadoctor

```bash
metaclaw doctor stop
```

## 飞书交互命令

在飞书私聊中给 Metadoctor 机器人发送以下命令：

| 命令 | 说明 |
|------|------|
| `status` / `状态` | 查看 MetaClaw 进程状态、PID、日志更新时间、内存 |
| `restart` / `重启` | 重启 MetaClaw |
| `logs [N]` / `日志 [N]` | 查看最近 N 行日志（默认 20 行） |
| `diagnose` / `诊断` | 完整健康诊断报告 |
| `help` / `帮助` | 显示命令列表 |

### 示例对话

```
你: status
Metadoctor: **Status: OK**
Process: Alive (PID: 12345)
Log updated: 12s ago
Memory: 256MB

你: logs 5
Metadoctor: Last 5 lines of run.log:
```
[INFO][2026-04-30 10:00:01][app.py:123] - Channel started
...
```

你: restart
Metadoctor: Restarting MetaClaw...
Metadoctor: MetaClaw restarted successfully.
```

## 告警行为

Metadoctor 会在以下情况发送飞书通知：

| 场景 | 告警级别 | 行为 |
|------|---------|------|
| MetaClaw 进程不存在 | **CRITICAL** | 通知用户，建议发送 `restart` |
| 日志超过 5 分钟无更新 | **WARNING** | 通知用户 MetaClaw 可能卡住 |
| 日志超过 15 分钟无更新 | **CRITICAL** | 通知用户建议检查或重启 |
| 内存超过 2048MB | **WARNING** | 通知用户内存使用过高 |

> **注意**：默认 `metadoctor_auto_restart` 为 `false`，即只告警不自动重启。需要手动在飞书发送 `restart` 命令。

## 故障排查

### Metadoctor 启动失败

```
Error: metadoctor_feishu_app_id and metadoctor_feishu_app_secret are required.
```

**解决**：检查 `config.json` 中是否正确填写了飞书 App ID 和 Secret。

### 收不到飞书消息

1. 检查飞书应用是否已发布，且你在可用范围内
2. 检查事件订阅中是否添加了 `im.message.receive_v1`
3. 检查是否选择了「使用长连接接收事件」
4. 查看 `metadoctor.log` 中的连接日志

### 收不到告警通知

1. 检查 `metadoctor_notify_open_id` 是否正确
2. 检查飞书应用是否有 `im:message` 权限
3. 告警只在状态变化时发送，不会重复刷屏

### lark_oapi 未安装

```
[Metadoctor] lark_oapi not installed, cannot start WebSocket
```

**解决**：
```bash
pip install lark-oapi
```

## 文件位置

| 文件 | 路径 |
|------|------|
| PID 文件 | `~/metaclaw/logs/.metadoctor.pid` |
| 日志文件 | `~/metaclaw/logs/metadoctor.log` |
| 配置文件 | `~/metaclaw/config.json` |
