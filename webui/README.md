# MC互通管家 · Web 控制面板（webui/）
> ⚠️ 本项目全部代码与内容由 AI 生成，仅供学习交流使用，请勿用于商业用途。


纯静态移动端网页，用于在 iPhone / Android 手机上通过浏览器远程控制局域网内的 MC-Bridge 桌面端。

- **零 CDN 依赖**：原生 HTML/CSS/JS，离线可用，无任何外部框架/字体/CDN 引用。
- **PWA 就绪**：含 `manifest.json`、`apple-touch-icon`、`theme-color`、`viewport-fit=cover`，可「添加到主屏幕」全屏启动。
- **不包含后端**：本目录只负责 UI，所有数据通过浏览器直接 `fetch` 到 `http://<lan_ip>:8765`（桌面端 WebAPI，CORS 已开放 `*`）。

---

## 文件清单

| 文件 | 说明 |
|---|---|
| `index.html` | 单页应用入口（首屏配对 + 控制台） |
| `style.css`  | 移动端优先的卡片式样式，主色青蓝 |
| `app.js`     | 全部业务逻辑：配对、轮询状态/日志、启停、配置 |
| `manifest.json` | PWA 清单（添加到主屏幕） |
| `icon.svg` / `icon-192.png` / `icon-512.png` | 应用图标 |
| `netlify.toml` | Netlify 部署配置（纯静态） |

---

## 使用流程

1. 在电脑上启动 **MC-Bridge 桌面端**，主界面会显示一个 **6 位数字连接码** 和一个二维码。
2. 用手机相机扫描该二维码（或手动打开本网页）：
   - 扫码打开的 URL 形如 `https://你的站点.netlify.app/?host=192.168.1.100&code=123456`，页面会自动完成配对。
   - 手动打开时，在首屏输入 6 位连接码，并在「高级」中填写桌面端的局域网 IP（例如 `192.168.1.100:8765`），点「连接」。
3. 配对成功后，`host + token` 会存进浏览器 `localStorage`，下次打开自动进入控制台。
4. 控制台可查看状态、启动/停止/重启服务器、查看实时日志、修改常用配置、查看在线玩家。
5. 点右上角「断开」会清除本地配对信息并回到首屏。

> 手机必须与电脑连接**同一个 Wi-Fi/局域网**。手机浏览器直连的是电脑局域网 IP，不经过公网。

---

## 部署到 Netlify（二选一）

### 方式 A：拖拽部署（最快）

1. 打开 <https://app.netlify.com/drop> （登录后）。
2. 把本 **`webui/` 整个目录** 直接拖到网页上。
3. Netlify 会自动分配一个 `https://xxx.netlify.app` 域名，立即可用。

### 方式 B：连接 Git 仓库

1. 在 Netlify 控制台点「Add new site → Import an existing project」，选择本仓库。
2. 构建命令留空，**Publish directory** 填：

   ```
   webui
   ```

3. 部署即可。`netlify.toml` 已内置正确的发布目录与缓存头，无需额外配置。

> 因为本站是 HTTPS 而桌面端是局域网 HTTP，现代浏览器会要求桌面端支持混合内容或用户手动允许。当前设计假定桌面端 CORS 已放行 `*`；若浏览器拦截 HTTP 混合内容，可在 iOS Safari 对站点「请求桌面网站」旁的混合内容提示中选择「允许」，或桌面端后续升级为 HTTPS。

---

## 本地调试

```bash
cd webui
python3 -m http.server 5173
# 浏览器打开 http://localhost:5173/
# 模拟扫码：http://localhost:5173/?host=192.168.1.100&code=123456
```

没有真实后端时，页面可以正常打开、渲染 UI；点击「连接」会提示连不上，属正常现象。

---

## API 对接约定

| 用途 | 方法 | 路径 | 鉴权 |
|---|---|---|---|
| 健康检查 | GET | `/api/v1/health` | 无 |
| 配对 | POST | `/api/v1/pair` `{code}` | 无 |
| 状态 | GET | `/api/v1/status` | Bearer token |
| 启动 | POST | `/api/v1/start` | Bearer token |
| 停止 | POST | `/api/v1/stop` | Bearer token |
| 重启 | POST | `/api/v1/restart` | Bearer token |
| 读配置 | GET | `/api/v1/config` | Bearer token |
| 写配置 | PUT | `/api/v1/config` | Bearer token |
| 日志 | GET | `/api/v1/logs?n=200&since=<n>` | Bearer token |

- 配对成功后返回 `{token: "..."}`，前端把 `host + token` 存入 `localStorage`。
- 后续所有请求带 `Authorization: Bearer <token>`；收到 401 自动清登录态并回首屏。
