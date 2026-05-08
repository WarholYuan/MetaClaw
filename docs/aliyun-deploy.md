# MetaClaw 阿里云服务器部署指南

## 一、服务器准备

### 1.1 服务器配置

| 项目 | 规格 |
|------|------|
| 实例类型 | u2a（初创企业优选） |
| CPU | 2 核 |
| 内存 | 4 GB |
| 系统盘 | 40 GB ESSD |
| 带宽 | 5 Mbps（按需可调） |
| 操作系统 | Ubuntu 22.04 LTS |
| 地域 | 选离目标用户最近的（如华东、华北） |

### 1.2 安全组配置

在阿里云控制台 → ECS 实例 → 安全组中放行以下端口：

| 端口 | 协议 | 用途 |
|------|------|------|
| 22 | TCP | SSH 登录 |
| 80 | TCP | Nginx HTTP |
| 443 | TCP | Nginx HTTPS |
| 9899 | TCP | Web 控制台（Nginx 代理后可关闭） |

### 1.3 SSH 登录

```bash
ssh root@你的服务器IP
```

建议首次登录后创建部署用户：

```bash
adduser deploy
usermod -aG sudo deploy
su - deploy
```

---

## 二、部署方式一：Docker（推荐）

### 2.1 安装 Docker

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | bash

# 启动并设置开机自启
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户加入 docker 组（免 sudo）
sudo usermod -aG docker $USER

# 退出重新登录使组权限生效
exit
```

### 2.2 创建项目目录

```bash
sudo mkdir -p /opt/metaclaw
cd /opt/metaclaw
```

### 2.3 创建 docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
services:
  metaclaw:
    image: warholyuan/metaclaw:latest
    container_name: metaclaw
    restart: unless-stopped
    ports:
      - "9899:9899"
    volumes:
      - metaclaw-data:/app/data
      - metaclaw-config:/app/config
    environment:
      - METACLAW_CONFIG_FILE=/app/config/config.json
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9899/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  metaclaw-data:
  metaclaw-config:
EOF
```

### 2.4 创建配置文件

```bash
# 创建配置目录
sudo docker volume create metaclaw-config

# 创建初始配置
sudo docker run --rm -v metaclaw-config:/app/config alpine sh -c 'cat > /app/config/config.json << "CONF"
{
  "channel_type": "feishu",
  "model": "MiniMax-M2.7",
  "agent": true,
  "web_console": true,
  "agent_workspace": "/app/workspace"
}
CONF'
```

### 2.5 编辑配置（填入真实参数）

```bash
# 找到 config.json 实际路径
CONFIG_PATH=$(sudo docker volume inspect metaclaw-config | grep Mountpoint | awk -F'"' '{print $4}')
sudo nano "${CONFIG_PATH}/config.json"
```

配置示例：

```json
{
  "channel_type": "feishu,qq",
  "model": "MiniMax-M2.7",
  "minimax_api_key": "你的API-Key",
  "agent": true,
  "agent_workspace": "/app/workspace",
  "web_console": true,
  "web_password": "你的控制台密码",
  "feishu_app_id": "你的飞书AppID",
  "feishu_app_secret": "你的飞书AppSecret",
  "feishu_token": "你的飞书Token",
  "feishu_event_mode": "websocket",
  "qq_app_id": "你的QQAppID",
  "qq_app_secret": "你的QQAppSecret"
}
```

### 2.6 启动服务

```bash
cd /opt/metaclaw
docker-compose up -d
```

### 2.7 验证

```bash
# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 测试 Web 控制台
curl http://localhost:9899/health
```

Web 控制台地址：`http://你的服务器IP:9899/chat`

---

## 三、部署方式二：脚本安装

### 3.1 安装依赖

```bash
# 更新系统
sudo yum upgrade -y

# 安装基础工具
sudo yum install -y git curl python3 python3-pip python3-venv
```

### 3.2 运行安装脚本

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/install.sh | bash
```

安装完成后目录结构：

```
~/.metaclaw/
├── src/          # 源码
├── venv/         # Python 虚拟环境
└── workspace/    # 配置和运行数据
    └── config.json
```

### 3.3 交互式配置

```bash
metaclaw setup
```

按提示选择：渠道 → 模型 → 填入 API Key → 开启 Agent 模式 → 设置密码。

### 3.4 手动编辑配置

```bash
nano ~/.metaclaw/workspace/config.json
```

### 3.5 启动服务

```bash
metaclaw start
```

---

## 四、systemd 服务管理（脚本安装方式）

创建系统服务实现开机自启和后台运行：

```bash
sudo tee /etc/systemd/system/metaclaw.service << 'EOF'
[Unit]
Description=MetaClaw AI Agent
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/.metaclaw/src/metaclaw
ExecStart=/home/deploy/.metaclaw/venv/bin/python -m app
Restart=always
RestartSec=10
Environment=PATH=/home/deploy/.local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF
```

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启动并设置开机自启
sudo systemctl start metaclaw
sudo systemctl enable metaclaw

# 常用命令
sudo systemctl status metaclaw   # 查看状态
sudo systemctl restart metaclaw  # 重启
sudo systemctl stop metaclaw     # 停止
journalctl -u metaclaw -f        # 查看日志
```

---

## 五、Nginx 反向代理

### 5.1 安装 Nginx

```bash
sudo apt install -y nginx
```

### 5.2 配置反向代理

```bash
sudo tee /etc/nginx/sites-available/metaclaw << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:9899;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF
```

```bash
# 启用站点
sudo ln -s /etc/nginx/sites-available/metaclaw /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 检查配置
sudo nginx -t

# 重载
sudo systemctl reload nginx
```

### 5.3 HTTPS（可选）

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 申请证书（需要域名已解析到服务器）
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo systemctl enable certbot.timer
```

---

## 六、渠道配置详解

### 6.1 飞书

在 `config.json` 中配置：

```json
{
  "channel_type": "feishu",
  "feishu_app_id": "cli_xxxxxx",
  "feishu_app_secret": "xxxxxx",
  "feishu_token": "xxxxxx",
  "feishu_event_mode": "websocket"
}
```

**推荐使用 `websocket` 模式**，无需公网 IP 和 Webhook 回调地址。

飞书开放平台配置步骤：
1. 登录 [飞书开放平台](https://open.feishu.cn) → 创建应用
2. 添加"机器人"能力
3. 订阅事件：`im.message.receive_v1`
4. 获取 App ID、App Secret，填入配置

### 6.2 QQ Bot

```json
{
  "channel_type": "qq",
  "qq_app_id": "xxxxxx",
  "qq_app_secret": "xxxxxx"
}
```

QQ 使用 WebSocket 长连接，无需公网 IP。

QQ 开放平台配置步骤：
1. 登录 [QQ 开放平台](https://q.qq.com) → 创建机器人
2. 获取 App ID 和 App Secret
3. 开启群聊/私聊消息权限

### 6.3 微信个人号

```json
{
  "channel_type": "weixin",
  "weixin_base_url": "https://你的ilink服务地址",
  "weixin_token": "xxxxxx"
}
```

微信个人号需要 ilink Bot 服务中转，首次启动会在终端显示二维码，用手机微信扫码登录。

### 6.4 多渠道同时运行

```json
{
  "channel_type": "feishu,qq"
}
```

用逗号分隔多个渠道，Web 控制台默认自动启动。

---

## 七、2C4G 内存优化

4GB 内存需合理分配，避免 OOM。以下是关键优化项：

### 7.1 创建 Swap 分区

```bash
# 创建 2GB swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永久生效
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 降低 swap 使用倾向（优先用物理内存）
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 7.2 限制 Docker 容器内存

修改 docker-compose.yml，增加内存限制：

```yaml
services:
  metaclaw:
    # ... 其他配置同上
    deploy:
      resources:
        limits:
          memory: 3G
        reservations:
          memory: 1G
```

### 7.3 控制并发会话数

在 `config.json` 中限制并发：

```json
{
  "max_concurrent_sessions": 10,
  "feishu_request_timeout_seconds": 600
}
```

### 7.4 定时清理临时文件

```bash
# 添加 cron 任务，每小时清理超过1小时的临时文件
(crontab -l 2>/dev/null; echo "0 * * * * find /tmp -name 'wx_media_*' -mmin +60 -delete 2>/dev/null") | crontab -
(crontab -l 2>/dev/null; echo "0 * * * * find /tmp -name '*.tmp' -mmin +120 -delete 2>/dev/null") | crontab -
```

### 7.5 内存监控告警

```bash
sudo tee /opt/metaclaw/memory-alert.sh << 'SCRIPT'
#!/bin/bash
# 内存使用超过 80% 时写入日志
USED=$(free | awk '/Mem/{printf("%.0f", $3/$2*100)}')
if [ "$USED" -gt 80 ]; then
    echo "$(date): Memory usage ${USED}% (threshold 80%)" >> /var/log/metaclaw-memory.log
fi
SCRIPT

chmod +x /opt/metaclaw/memory-alert.sh
(crontab -l 2>/dev/null; echo "*/2 * * * * /opt/metaclaw/memory-alert.sh") | crontab -
```

---

## 八、日常运维

### 8.1 Docker 方式

```bash
cd /opt/metaclaw

docker-compose logs -f          # 实时查看日志
docker-compose logs --tail 200  # 最近200行
docker-compose ps               # 服务状态
docker-compose restart          # 重启

# 更新版本
docker-compose pull
docker-compose up -d

# 备份数据
sudo docker run --rm -v metaclaw-config:/app/config -v $(pwd)/backup:/backup alpine tar czf /backup/config-$(date +%Y%m%d).tar.gz /app/config
```

### 8.2 脚本安装方式

```bash
metaclaw status     # 状态
metaclaw logs       # 日志
metaclaw restart    # 重启
metaclaw stop    # 关闭
metaclaw start    # 启动
metaclaw-update     # 更新版本
```

### 8.3 健康检查脚本

```bash
sudo tee /opt/metaclaw/monitor.sh << 'SCRIPT'
#!/bin/bash
HEALTH_URL="http://localhost:9899/health"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ "$STATUS" != "200" ]; then
    echo "MetaClaw health check failed (HTTP $STATUS) at $(date)"
    cd /opt/metaclaw && docker-compose restart
fi
SCRIPT

chmod +x /opt/metaclaw/monitor.sh
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/metaclaw/monitor.sh >> /var/log/metaclaw-monitor.log 2>&1") | crontab -
```

---

## 九、故障排查

| 问题 | 排查命令 | 常见原因 |
|------|----------|----------|
| 服务无法启动 | `docker-compose logs` 或 `journalctl -u metaclaw` | 端口占用、配置错误 |
| 端口被占用 | `sudo lsof -i :9899` | 旧进程未退出 |
| 飞书连接失败 | 查看日志 `[FeiShu]` | App ID/Secret 错误 |
| QQ 连接失败 | 查看日志 `[QQ]` | App ID/Secret 错误 |
| API 调用失败 | 查看日志中 `error` | API Key 无效或过期 |
| OOM 崩溃 | `dmesg \| grep -i oom` | 内存不足，检查 swap 是否生效 |
| 磁盘满 | `df -h` | 临时文件堆积，清理 /tmp |

### 内存排查

```bash
# 实时内存
watch -n 5 free -h

# Docker 容器资源占用
docker stats metaclaw

# 查看进程内存排序
ps aux --sort=-%mem | head -10
```

---

## 十、安全清单

- [ ] 修改 SSH 默认端口或使用密钥登录
- [ ] 设置 Web 控制台密码（`web_password`）
- [ ] 安全组仅放行必要端口
- [ ] 启用 HTTPS（Certbot）
- [ ] config.json 权限设为 600：`chmod 600 config.json`
- [ ] 定期更新系统：`sudo apt update && sudo apt upgrade -y`
- [ ] API Key 不写入版本控制
- [ ] 定期备份 workspace 数据
