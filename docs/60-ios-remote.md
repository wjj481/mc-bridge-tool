# 60 · iOS 远程控制端说明

> 📌 iOS 端在本项目里**只做远程控制，不做服务器宿主**。
> 协议设计细节见 [ios/remote_api_design.md](../ios/remote_api_design.md)。

---

## 为什么 iOS 不能当服务器？

iPhone / iPad 受 iOS 沙盒限制，**无法运行 JVM**，因此不能跑 Paper / Geyser / Floodgate。这不是本工具的问题，是苹果系统级别的限制。详见 [40-faq.md](40-faq.md) 的 iOS 专节。

所以本工具在 iOS 上的定位是：

> 🎛️ **一台跑在你 iPhone 上的遥控器，远程控制另一台已经在跑 MC 服务器的电脑 / 安卓 / 云主机。**

---

## 典型使用场景

```
┌──────────────┐   局域网/WAN    ┌────────────────────┐
│  iPhone/iPad │ ◄── HTTP ────► │  家里的 Windows 电脑 │
│  (本工具 App) │   token 认证    │  跑 Paper+Geyser    │
└──────────────┘                 └────────────────────┘
                                          ▲
                                          │ UDP 19132 / TCP 25565
                                          │
                                 ┌────────┴─────┐
                                 │ 手机/平板基岩版 │
                                 │ 朋友的 Java 版  │
                                 └──────────────┘
```

1. 你家里的电脑开着 MC Bridge Tool 桌面端，服务器正在跑。
2. 出门在外，掏出 iPhone，打开本工具 iOS App。
3. 输入家里电脑的 IP + 控制 token，就能：
   - 看服务器状态（在线玩家、内存、TPS）
   - 一键开 / 关 / 重启
   - 改配置（端口、内存、难度、MOTD）
   - 看实时日志
   - 发游戏内命令（`/say`、`/op`、`/ban` 等）

---

## 控制端能做什么

| 功能 | HTTP 端点 | 说明 |
|------|-----------|------|
| 查看状态 | `GET /api/v1/status` | 运行状态、在线玩家、内存、端口 |
| 启动服务器 | `POST /api/v1/start` | 调用桌面端 ServerManager.start() |
| 停止服务器 | `POST /api/v1/stop` | 优雅停止，超时强杀 |
| 重启服务器 | `POST /api/v1/restart` | stop + start |
| 读取配置 | `GET /api/v1/config` | 拿回 server.properties 等配置 |
| 写入配置 | `PUT /api/v1/config` | 保存新配置 |
| 查看日志 | `GET /api/v1/logs?n=200` | tail 最近 N 行 |
| 发送命令 | `POST /api/v1/command` | 向 stdin 写命令 |
| 检查更新 | `GET /api/v1/updates` | 对比 Paper/Geyser/Floodgate 版本 |
| 备份配置 | `POST /api/v1/backup` | 触发一次备份 |

完整 JSON 格式、错误码、token 认证方式见 [ios/remote_api_design.md](../ios/remote_api_design.md)。

---

## 在桌面端开启远程控制

桌面端设置页里有一个「远程控制」开关：

1. 打开「启用远程控制 API」
2. 工具会生成一个随机 token（一长串字母数字），**只显示一次**，自己抄下来。
3. 监听地址默认 `0.0.0.0:8765`（局域网内可访问）。
4. 如果要在外网访问，需要在路由器上把 8765 端口转发到这台电脑，或者用 frp。

> ⚠️ **不要把 8765 直接暴露到公网而不配 HTTPS**。token 是明文在 HTTP 头里传的，裸 HTTP 等于把密码发在大街上。公网部署请前置 nginx + 证书，用 HTTPS。

---

## iOS App 的实现方案

本工具不提供现成的 IPA（苹果开发者账号每年要 99 美元，且本项目是个人开源项目）。你有三条路：

### 方案 A：用 Web 远程控制台（最简单）

桌面端自带一个内嵌的 Web 控制台页面（`http://<电脑IP>:8765/`）。你直接用 iPhone 的 Safari 打开这个网址，输入 token 登录，就能完成所有远程控制操作。**不需要装任何 App**。

这是推荐方案，零成本。

### 方案 B：用 Kivy-iOS 把 Android 那份 Kivy 代码跑在 iOS 上

本项目 Android 端用的是 Kivy 框架。理论上同一份 Python UI 代码可以通过 [Kivy-iOS / kivy-ios](https://github.com/kivy/kivy-ios) 工具链编译成 iOS 工程：

```bash
git clone https://github.com/kivy/kivy-ios
cd kivy-ios
./toolchain.py build python3 kivy requests
./toolchain.py create mcbridge-ios /path/to/mc-bridge-tool
```

然后用 Xcode 打开生成的 `.xcodeproj`，用自己的 Apple ID 签名跑。

### 方案 C：用 Xcode 写一个原生 SwiftUI 客户端

如果你熟悉 iOS 开发，可以自己写一个 SwiftUI 壳，直接调上面的 HTTP API。API 就是简单的 JSON over HTTP，一天就能写出来。

---

## Xcode 自签名 / 爱思助手安装大纲

如果走方案 B 或 C，编译出 `.ipa` 后怎么装到自己手机？

### 1. 免费 Apple ID 自签名（7 天有效期）

1. 用一根数据线把 iPhone 连到 Mac。
2. 打开 Xcode，菜单 → Xcode → Settings → Accounts，登录你的 Apple ID（免费账号即可）。
3. 打开工程，在 Signing & Capabilities 里选你的 Team。
4. 改一个独特的 Bundle Identifier（不要用 `org.kivy.*` 这种别人用过的）。
5. 点 Product → Run，Xcode 会自动编译并安装到手机。
6. iPhone 上：设置 → 通用 → VPN 与设备管理 → 信任你的开发者证书。

> 免费账号签名的 App 7 天后会失效，需要重新连 Xcode 跑一次。

### 2. 爱思助手 / AltStore 长期签名

如果你没有 Mac，或者不想每次 7 天重签，可以用：

- **AltStore**：装 AltServer 到 Windows / Mac，手机插线刷新签名，免费证书可续期。
- **爱思助手**：Windows 下图形化工具，能帮你把 IPA 装到非越狱 iPhone，本质也是用你的 Apple ID 签。

### 3. 越狱设备（不推荐）

如果你 iPhone 已经越狱，可以直接用 Cydia 装 OpenJDK，把 iOS 当成一台 Linux 服务器。但越狱会失去保修、降低安全性、无法升级官方 iOS，**本项目不提供越狱方案支持**。

---

## 安全建议

- 控制 token 当密码对待，不要截图发群里。
- 远程控制 API 默认只监听局域网。要外网用，请套 HTTPS。
- 定期在设置里「重置 token」，旧 token 立刻失效。
- 不要在公共 Wi-Fi 下裸 HTTP 连远程控制。
