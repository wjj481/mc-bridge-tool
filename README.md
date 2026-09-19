# MC Bridge Tool

> 把 Minecraft Java 版 / 基岩版互通服务器做成「全按钮、零命令行」的 GeyserMC 全家桶管理器。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)](#)
[![Downloads](https://img.shields.io/github/downloads/wjj481/mc-bridge-tool/total.svg)](https://github.com/wjj481/mc-bridge-tool/releases)

---

## 这是什么？

MC Bridge Tool 是一个图形化的 Minecraft 互通服务器管理工具。它把 **Paper 服务端 + Geyser-Spigot 插件 + Floodgate-Spigot 插件** 这套互通组合的下载、安装、配置、启动、停止、更新、备份全部封装成按钮操作，**不需要你敲任何一条命令行**。

- 🖱️ 一键部署：自动下载 Paper、Geyser、Floodgate，自动写好配置，自动同意 EULA
- 🎛️ 图形化配置：版本、端口、内存、难度、游戏模式、白名单、MOTD 全部可视化
- 🟢 一键启停：开始 / 停止 / 重启，带日志实时滚动
- 📊 状态监控：在线玩家、内存占用、端口监听、TPS 一眼看完
- 📦 组件更新备份：一键检查更新、一键更新、配置备份与还原

互通原理：**Paper（Java 版服务端）+ Geyser-Spigot（让基岩版玩家连进来）+ Floodgate-Spigot（基岩版玩家以 Xbox 账号或离线身份免正版验证加入）**。

---

## 功能清单

| 模块 | 能力 |
|------|------|
| 一键部署 | 自动选择匹配的 JDK、下载 Paper / Geyser / Floodgate、生成初始配置、同意 EULA |
| 图形化配置 | server.properties、Geyser config.yml、Floodgate config 全部可视化编辑 |
| 一键启停 | 启动 / 停止 / 重启 / 发命令 / 实时日志 |
| 状态监控 | 运行状态、在线玩家、内存、端口监听、TPS |
| 组件更新备份 | 在线检查 Paper / Geyser / Floodgate 新版本，一键更新；配置一键备份 / 还原 |

---

## 平台支持矩阵

| 平台 | 服务器宿主（跑 JVM） | 管理端 | 备注 |
|------|:---:|:---:|------|
| Windows 64 位 | ✅ | ✅ 桌面 tkinter | 主力支持平台 |
| Windows 32 位 | ⚠️ 需 Python 3.10 32 位 + 32 位 JDK | ✅ | 仅维护，不推荐 |
| macOS x86_64 (Intel) | ✅ | ✅ 桌面 tkinter | |
| macOS arm64 (Apple Silicon) | ✅ | ✅ 桌面 tkinter | 原生 arm64 构建 |
| Linux (x86_64) | ✅ | ✅ 桌面 tkinter | 服务器无 GUI 时可用 headless 模式 |
| Android | ✅ Termux 内运行 | ✅ Kivy 原生 App | 见 [50-android-termux](docs/50-android-termux.md) |
| iOS (iPhone / iPad) | ❌ **不能当服务器宿主** | ✅ 远程控制 App | 见 [60-ios-remote](docs/60-ios-remote.md) |

> ⚠️ **重要**：iPhone / iPad 受 iOS 沙盒限制，**无法运行 JVM**，因此不能直接当服务器电脑用。iOS 端本工具仅提供「远程控制」能力，用来远程管理一台已在运行的服务器。

---

## 快速上手

### 桌面端（Windows / macOS / Linux）

1. 安装 Java：根据你要跑的 Paper 版本装对应 JDK——Paper 26.x 需要 **Java 25**，1.21.x 需要 **Java 21**。
2. 下载本工具对应平台的二进制（Releases 页），或从源码运行 `python desktop/main.py`。
3. 打开工具 → 点「一键部署」→ 等下载完成 → 在图形界面里改好配置 → 点「启动」。

详细图文教程见：

- [快速开始：从零开服](docs/10-quickstart.md)
- [网络与端口配置](docs/20-network.md)
- [基岩版手机怎么加服](docs/30-connect-bedrock.md)
- [常见问题 FAQ](docs/40-faq.md)

### 安卓

- [Android Termux 开服教程](docs/50-android-termux.md)

### iOS

- [iOS 远程控制端说明](docs/60-ios-remote.md)
- [iOS 远程控制协议设计](ios/remote_api_design.md)

---

## 技术栈

- **核心库**：`mcbridge/`（纯 Python，平台无关，不依赖 GUI 框架）
- **桌面端**：`desktop/`（Python 标准库 tkinter，零额外依赖）
- **Android 端**：`android/`（Kivy）
- **iOS 端**：`ios/`（远程控制，HTTP + token 认证）
- **服务端组件**：PaperMC + Geyser-Spigot 2.11.3 + Floodgate-Spigot 2.2.5

---

## 下载源说明

| 组件 | 官方 API | 说明 |
|------|----------|------|
| Paper | `https://fill.papermc.io/v3/projects/paper` | 旧 v2 API 已下线（sunset），统一走 v3 |
| Geyser | `https://download.geysermc.org/v2/projects/geyser` | 当前最新 2.11.3 |
| Floodgate | `https://download.geysermc.org/v2/projects/floodgate` | 当前最新 2.2.5 |

Java 25 / Java 21 与 Paper 版本对应关系：

| Paper 版本 | 所需 Java |
|------------|-----------|
| 26.x | Java 25 |
| 1.21.x | Java 21 |

---

## 端口

| 服务 | 协议 | 端口 |
|------|------|------|
| Java 版玩家连接 | TCP | 25565 |
| 基岩版玩家连接 | UDP | 19132 |

---

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。

## 免责声明

本项目仅供个人学习与交流使用，**不提供任何商用、私服运营、商业化部署的保障或技术支持**。使用本工具搭建的服务器，请自行遵守 Mojang / Microsoft EULA 及当地法律法规。作者不对因使用本工具导致的任何数据损失、法律责任或服务纠纷承担责任。

## 截图

UI 截图请放入 `assets/` 目录，命名建议：

- `assets/screenshot-main.png` — 主界面
- `assets/screenshot-deploy.png` — 一键部署进度
- `assets/screenshot-config.png` — 图形化配置页
- `assets/screenshot-status.png` — 状态监控面板

> 仓库当前尚未包含截图，欢迎贡献者在 Releases 后补充。

## 仓库地址

GitHub：[wjj481/mc-bridge-tool](https://github.com/wjj481/mc-bridge-tool)
