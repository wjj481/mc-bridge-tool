# 安卓手机当 MC 互通服务器 · 完整图文教程

> 方案：**Termux + openjdk + Paper + Geyser + Floodgate**
> 目标：零命令行，全按钮化。
> 适用：安卓 8.0+（arm64 手机/平板）。iPhone 不适用（见 `ios/`）。

---

## 0. 它是怎么工作的？

```
┌──────────────────────── 你的安卓手机 ────────────────────────┐
│                                                              │
│  Termux（终端容器）                                          │
│    ├─ openjdk-21     ← 跑 Java 服务端                        │
│    └─ ~/mcbridge/server/                                    │
│         ├─ paper.jar                                       │
│         ├─ plugins/Geyser-Spigot.jar   (基岩互通)           │
│         └─ plugins/floodgate-spigot.jar (离线基岩登录)      │
│                                                              │
│  「MC互通管家」APK（本仓库 android/main.py 打包）            │
│    └─ 4 个按钮页：环境 / 部署 / 配置 / 控制台                │
└──────────────────────────────────────────────────────────────┘
            ↑ 局域网 UDP:19132（基岩版） / TCP:25565（Java 版）
```

APK 只是遥控器，真正干活的 Java 进程在 Termux 里。

---

## 1. 安装 Termux

| 渠道 | 地址 | 说明 |
|---|---|---|
| F-Droid（推荐） | <https://f-droid.org/packages/com.termux/> | 官方持续更新 |
| GitHub Release | termux/termux-app | 备用 |

> **千万别装 Google Play 上那个 2020 年停更的 Termux**，`pkg` 源会 404。

装完先**先别开它**，下一步装遥控器 App。

---

## 2. 安装「MC互通管家」APK

APK 不在你手里——由 CI 在你打 git tag 时自动产出：

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions 跑完后，去仓库 **Releases** 页下载 `mcbridge-1.0.0-debug.apk`。
手机上点「允许安装未知来源」→ 安装。

---

## 3. 四步开服（全按钮）

### 第 1 步 · 环境页
打开 App → 底部点 **「环境」**：
- 点 **「一键安装 openjdk-21」**。
  App 会在 Termux 里自动跑 `pkg install openjdk-21 python`。
- 等 2~5 分钟 → 点 **「刷新检测」**，看到 `Java 21` 就 OK。

> 想跑 Paper 26.x？先在 Termux 里 `pkg install openjdk-25`，
> 部署页选 26.x 即可（Java 21 跑 26.x 会报 UnsupportedClassVersionError）。

### 第 2 步 · 部署页
底部点 **「部署」**：
- 顶部下拉选 Paper 版本（默认 `1.21.4`，配 Java 21 最稳）。
- 点 **「一键部署」**。进度条走到 100%，日志区显示「部署完成 ✅」。
  自动：下 paper.jar、Geyser、Floodgate → 写配置 → 同意 eula。

### 第 3 步 · 配置页（可选）
底部点 **「配置」**：
- 内存默认 Xms 1G / Xmx 2G，手机 6G 内存可给到 3G。
- 改 MOTD、难度、最大玩家 → **「保存配置」**。

### 第 4 步 · 控制台页
底部点 **「控制台」**：
- 点 **「启动」**。状态面板 3 秒自动刷新，出现 🟢 即成功。
- 日志区滚动显示 Paper 启动日志，看到 `Done!` 就是真的起来了。

---

## 4. 朋友怎么连进来？

| 端 | 连接地址 |
|---|---|
| 基岩版（手机 / Win10 商店版 / Xbox / Switch） | `手机局域网IP:19132` |
| Java 版（PC 原版启动器） | `手机局域网IP:25565` |

**查手机 IP**：Termux 里跑 `ip addr show wlan0`，找 `inet 192.168.x.x`。

> 同 Wi-Fi 下直接连。想让外网朋友连？需要路由器做端口转发（25565 TCP / 19132 UDP），
> 或用 frp / 内网穿透。

---

## 5. 常见问题

| 现象 | 原因 / 解决 |
|---|---|
| 启动报 `UnsupportedClassVersionError` | Paper 版本和 Java 不匹配。1.21.x 用 Java 21，26.x 用 Java 25。 |
| `pkg install` 卡住 / 404 | Termux 版本太旧，换 F-Droid 版；或先 `pkg update`。 |
| 基岩版连不上 | 检查 19132 是 **UDP**；手机防火墙/省电模式杀后台。 |
| 手机发烫 / 掉电 | 调低 Xmx（1G 即可），关其他 App；这是正常的。 |
| App 一打开就闪退 | 大概率核心库 mcbridge 没拷进打包目录（CI 已处理；本地打包见 android/README.md）。 |

---

## 6. 谁在维护什么？

| 目录 | 谁负责 |
|---|---|
| `mcbridge/` | 核心库（下载 / 启停 / 监控 / 配置），本任务不改 |
| `android/` | 本仓库 Android 端 GUI + 打包 |
| `desktop/` | 桌面端 |
| `ios/` | iOS 端（另一方案，Termux 不可用） |
| `docs/` | 契约 + 本文档 |
