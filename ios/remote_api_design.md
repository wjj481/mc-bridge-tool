# iOS 远程控制 API 设计

> 本文件定义 iOS 远程控制端（以及任何第三方客户端）与 MC Bridge Tool 桌面端之间的 HTTP 控制面协议。
> 桌面端在 `mcbridge/` 内实现一个轻量 HTTP 服务（建议基于 Python 标准库 `http.server`，不引入 Flask/FastAPI 依赖），监听默认端口 `8765`。

---

## 0. 设计原则

- **iOS 不能跑 JVM**，所以 iOS 端只是「遥控器」，所有重活都在桌面端完成。
- 协议尽量简单：HTTP + JSON，token 放在 `Authorization` 头里。
- 不引入 WebSocket，日志推送用轮询（`GET /logs?since=<n>`）。
- 桌面端是服务端，iOS 端是客户端。
- 所有响应统一 JSON，错误码用 HTTP 状态码 + 业务 `code` 字段。

---

## 1. 基础约定

| 项 | 值 |
|----|----|
| 默认监听地址 | `0.0.0.0:8765` |
| 路径前缀 | `/api/v1` |
| 编码 | UTF-8 |
| 请求体 | `application/json; charset=utf-8` |
| 响应体 | `application/json; charset=utf-8` |
| 时间戳 | Unix 秒（整数） |

### 认证

所有请求（除 `/health` 外）必须带 HTTP 头：

```
Authorization: Bearer <TOKEN>
```

TOKEN 由桌面端在「启用远程控制」时随机生成，32 字节 URL-safe base64。校验失败返回 `401 Unauthorized`。

### 通用错误响应

```json
{
  "ok": false,
  "code": "SERVER_NOT_RUNNING",
  "message": "服务器未在运行",
  "detail": "..."
}
```

HTTP 状态码约定：

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | token 缺失 / 错误 |
| 403 | 权限不足（如未启用远程控制） |
| 404 | 资源不存在 |
| 409 | 状态冲突（如服务器已在运行时再 start） |
| 500 | 服务端内部错误 |

---

## 2. 端点列表

### 2.1 健康检查（无需认证）

```
GET /api/v1/health
```

响应：

```json
{
  "ok": true,
  "service": "mcbridge-remote",
  "version": "1.0.0",
  "time": 1726732800
}
```

---

### 2.2 查看服务器状态

```
GET /api/v1/status
```

响应：

```json
{
  "ok": true,
  "running": true,
  "players_online": 3,
  "players_max": 20,
  "players_list": ["Steve", "Alex", "Herobrine"],
  "mem_used_mb": 1024,
  "mem_total_mb": 2048,
  "java_port_listening": true,
  "bedrock_port_listening": true,
  "tps": 19.98,
  "uptime_seconds": 3600
}
```

---

### 2.3 启动服务器

```
POST /api/v1/start
```

请求体（可选）：

```json
{
  "java_path": null,
  "jvm_extra": ["-Dlog4j2.formatMsgNoLookups=true"]
}
```

响应（202 Accepted）：

```json
{
  "ok": true,
  "message": "启动中",
  "pid": 12345
}
```

如果已经在运行，返回 `409`：

```json
{ "ok": false, "code": "ALREADY_RUNNING", "message": "服务器已在运行" }
```

---

### 2.4 停止服务器

```
POST /api/v1/stop
```

请求体（可选）：

```json
{ "timeout": 30 }
```

响应：

```json
{ "ok": true, "message": "已停止" }
```

未运行时返回 `409`：

```json
{ "ok": false, "code": "NOT_RUNNING", "message": "服务器未在运行" }
```

---

### 2.5 重启服务器

```
POST /api/v1/restart
```

请求体（可选）：

```json
{ "timeout": 30 }
```

响应：

```json
{ "ok": true, "message": "重启中" }
```

---

### 2.6 读取配置

```
GET /api/v1/config
```

响应（对应 `mcbridge.config.ServerConfig`）：

```json
{
  "ok": true,
  "server_dir": "/home/user/MCServer",
  "java_port": 25565,
  "bedrock_port": 19132,
  "online_mode": true,
  "floodgate_enabled": true,
  "xms": "1G",
  "xmx": "2G",
  "difficulty": "normal",
  "gamemode": "survival",
  "motd": "MC Bridge Server",
  "max_players": 20,
  "whitelist": false,
  "level_name": "world",
  "view_distance": 10
}
```

---

### 2.7 写入配置

```
PUT /api/v1/config
```

请求体（部分字段更新，只传要改的）：

```json
{
  "motd": "我家的小服务器",
  "max_players": 10,
  "xmx": "3G"
}
```

响应：

```json
{ "ok": true, "message": "配置已保存，重启后生效" }
```

> 配置修改不会自动重启服务器。要生效需要再调 `/restart`。

---

### 2.8 查看日志

```
GET /api/v1/logs?n=200&since=1234
```

查询参数：

- `n`：返回最近 N 行，默认 200，最大 1000。
- `since`：返回行号大于该值的日志（用于增量拉取）。

响应：

```json
{
  "ok": true,
  "lines": [
    {"n": 1234, "time": "2026-09-19T13:00:01", "level": "INFO", "text": "[Server thread/INFO]: Done (3.123s)!"}
  ],
  "next_since": 1434
}
```

---

### 2.9 发送游戏内命令

```
POST /api/v1/command
```

请求体：

```json
{ "command": "say 大家好" }
```

响应：

```json
{ "ok": true, "message": "命令已发送" }
```

未运行时返回 `409`。

---

### 2.10 检查组件更新

```
GET /api/v1/updates
```

响应：

```json
{
  "ok": true,
  "paper": {
    "current": "1.21.4",
    "latest": "1.21.4",
    "update_available": false
  },
  "geyser": {
    "current": "2.11.3",
    "latest": "2.11.3",
    "update_available": false
  },
  "floodgate": {
    "current": "2.2.5",
    "latest": "2.2.5",
    "update_available": false
  }
}
```

---

### 2.11 一键更新组件

```
POST /api/v1/update
```

请求体：

```json
{ "component": "geyser" }
```

`component` 取值：`paper` / `geyser` / `floodgate`。

响应（202）：

```json
{ "ok": true, "message": "更新中", "component": "geyser" }
```

更新完成后需要重启服务器才生效。

---

### 2.12 备份配置

```
POST /api/v1/backup
```

响应：

```json
{
  "ok": true,
  "file": "backups/backup_20260919_130000.zip",
  "size_bytes": 12345678
}
```

---

### 2.13 列出备份

```
GET /api/v1/backups
```

响应：

```json
{
  "ok": true,
  "backups": [
    {"file": "backups/backup_20260919_130000.zip", "size_bytes": 12345678, "time": 1726732800}
  ]
}
```

---

## 3. iOS 端典型调用流程

### 3.1 首次登录

1. 用户在 App 里填：服务器地址（如 `http://192.168.1.10:8765`）+ token。
2. App 调 `GET /api/v1/health` 验证网络通。
3. App 调 `GET /api/v1/status` 验证 token 正确。
4. 成功后把地址和 token 存在 iOS Keychain 里。

### 3.2 仪表盘

- 进入 App 首页 → 每 3 秒轮询 `GET /api/v1/status`
- 显示：运行状态灯、在线玩家列表、内存条、TPS、两个端口监听图标
- 底部三个大按钮：启动 / 停止 / 重启

### 3.3 日志页

- 进入日志页 → 调 `GET /api/v1/logs?n=200`
- 之后每 2 秒用 `since=<next_since>` 增量拉新日志
- 自动滚动到底部，用户上滑暂停自动滚动

### 3.4 配置页

- 进入配置页 → `GET /api/v1/config` 填表单
- 用户改完 → `PUT /api/v1/config`
- 提示「重启后生效」，弹「立即重启？」

### 3.5 命令页

- 一个输入框 + 发送按钮
- 回车 → `POST /api/v1/command`
- 下方显示最近 20 条自己发的命令

---

## 4. 安全注意事项

1. **token 就是密码**。桌面端生成时只展示一次，用户复制到 iOS App。
2. **默认只监听局域网**。如果要外网访问：
   - 推荐前面放 nginx 做 HTTPS 终结。
   - 不要把 8765 端口直接裸暴露到公网。
3. **速率限制**：桌面端默认对每个 IP 限流 60 次/分钟，防止 token 泄露后被暴力扫描。
4. **操作审计**：所有 start/stop/restart/command 调用都会写进桌面端日志。
5. **重置 token**：桌面端设置页可一键重置 token，旧 token 立刻失效。
6. **不要把 token 硬编码进 App**。iOS App 只把 token 存在 iCloud Keychain。

---

## 5. 版本演进

- v1（当前）：以上全部端点。
- v2 预留：WebSocket 实时日志推送、多人协同（多设备同时控制）、TLS 自签证书自动信任。
