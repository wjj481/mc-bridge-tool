# iOS 端：远程控制

> 📌 本目录下的 iOS 相关设计，是把 iPhone / iPad 当作**遥控器**，而不是服务器。
> 完整教程见 [docs/60-ios-remote.md](../docs/60-ios-remote.md)。

---

## 一句话说明

**iPhone / iPad 因为 iOS 沙盒限制，无法运行 JVM，不能直接当 Minecraft 服务器宿主。**

本工具在 iOS 上只做一件事：通过 HTTP + token 认证，远程控制一台已经在跑 MC 服务器的电脑（Windows / macOS / Linux）或安卓手机（Termux）。

---

## 为什么不能在 iOS 上跑 JVM？

| 原因 | 说明 |
|------|------|
| 沙盒禁止 | iOS 不允许第三方 App 启动独立的 JVM 进程，也不允许嵌入完整 Java 运行时 |
| 没有 Termux | 安卓有 Termux 可以装 OpenJDK；iOS 没有等价物 |
| 审核拒绝 | 任何「在 App 里跑 JVM」的 App 都会被 App Store 拒绝 |
| 越狱不可取 | 越狱理论可行，但失去保修、不安全、无法升级官方系统，不推荐 |

结论：**服务器请跑在电脑或安卓上，iPhone 只做客户端 + 遥控器。**

---

## 控制面协议

详见 [remote_api_design.md](remote_api_design.md)。简要列一下：

| 能力 | 端点 | 方法 |
|------|------|------|
| 健康检查 | `/api/v1/health` | GET |
| 服务器状态 | `/api/v1/status` | GET |
| 启动 | `/api/v1/start` | POST |
| 停止 | `/api/v1/stop` | POST |
| 重启 | `/api/v1/restart` | POST |
| 读配置 | `/api/v1/config` | GET |
| 写配置 | `/api/v1/config` | PUT |
| 日志 | `/api/v1/logs` | GET |
| 发命令 | `/api/v1/command` | POST |
| 检查更新 | `/api/v1/updates` | GET |
| 更新组件 | `/api/v1/update` | POST |
| 备份 | `/api/v1/backup` | POST |

认证方式：HTTP 头 `Authorization: Bearer <TOKEN>`，token 在桌面端「启用远程控制」时生成。

---

## 三种 iOS 客户端方案

### 方案 A：Web 控制台（零安装，推荐）

桌面端自带一个内嵌 Web 控制台，直接在 iPhone Safari 里打开：

```
http://<开服电脑IP>:8765/
```

输入 token 即可使用，功能和原生 App 完全一致。**不需要装任何东西。**

### 方案 B：Kivy-iOS 编译（复用 Android 代码）

本项目 Android 端用 Kivy 写。可以用 [kivy-ios](https://github.com/kivy/kivy-ios) 工具链把同一份 Python UI 编译成 Xcode 工程：

```bash
git clone https://github.com/kivy/kivy-ios
cd kivy-ios
./toolchain.py build python3 kivy requests
./toolchain.py create mcbridge-ios /path/to/mc-bridge-tool
open mcbridge-ios-ios/mcbridge-ios.xcodeproj
```

需要 macOS + Xcode。

### 方案 C：SwiftUI 原生重写

如果想做一个上架 App Store 的原生 App，可以用 SwiftUI 调上面的 HTTP API，工作量不大（核心就是几十个按钮 + 一个 JSON 解析）。

---

## Xcode 自签名 / 爱思助手安装大纲

### 免费 Apple ID 签名（7 天有效）

1. Mac 上装 Xcode，登录免费 Apple ID（Xcode → Settings → Accounts）。
2. 数据线连 iPhone，在 Xcode 里打开 `.xcodeproj`。
3. Signing & Capabilities 里选自己的 Team，Bundle Identifier 改成独特值。
4. Product → Run，自动编译并安装到手机。
5. iPhone 设置 → 通用 → VPN 与设备管理 → 信任开发者证书。
6. 7 天后需重新连 Xcode 跑一次续期。

### AltStore / 爱思助手长期签名

- **AltStore**：Windows / Mac 装 AltServer，手机插线刷新签名，可后台续期。
- **爱思助手**：Windows 图形化工具，用自己的 Apple ID 把 IPA 装到非越狱 iPhone。

### 越狱（不推荐）

越狱后理论上可以装 OpenJDK 把 iOS 当服务器跑。本项目不提供越狱相关支持，也不建议普通用户尝试。

---

## 安全提醒

- 远程控制 API 监听 `8765` 端口，默认只在局域网可用。
- 要外网访问请套 nginx + HTTPS，**不要裸 HTTP 暴露到公网**。
- token 当密码保管，泄露了立刻在桌面端「重置 token」。
- 桌面端默认限流 60 次/分钟，防爆破。

---

## 目录结构

```
ios/
├── README.md                 ← 本文件
└── remote_api_design.md     ← HTTP 协议完整定义
```
