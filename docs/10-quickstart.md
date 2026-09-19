# 10 · 快速开始：从零开服

本教程带你从一台干净的 Windows / macOS / Linux 电脑，完成安装 Java → 装工具 → 一键部署 → 改配置 → 开服的完整流程。

---

## 第 1 步：安装 Java（JDK）

MC Bridge Tool 本身是 Python 写的，但它管理的 Minecraft 服务端跑在 JVM 上，所以你必须先装 Java。

### 选对 Java 版本

| 你要跑的 Paper 版本 | 需要的 Java |
|---------------------|-------------|
| Paper 26.x | **Java 25** |
| Paper 1.21.x | **Java 21** |

推荐下载 LTS 版本（Java 21 是当前长期支持版，社区兼容性最好）。如果你不确定选哪个，先装 **Java 21**，工具默认部署的是 1.21.4。

### 下载地址

- [Adoptium Temurin JDK 下载页](https://adoptium.net/temurin/releases/)（推荐，免费开源）
- [Oracle JDK 下载页](https://www.oracle.com/java/technologies/downloads/)（需注册）

### 安装后验证

打开终端 / 命令提示符，输入：

```bash
java -version
```

看到类似下面的输出就说明装好了：

```
openjdk version "21.0.3" 2024-04-16 LTS
```

> 如果你装了多个 Java 版本也没关系，MC Bridge Tool 启动时会自动检测并推荐最匹配当前 Paper 版本的那个。

---

## 第 2 步：安装 MC Bridge Tool

### 方式 A：下载预编译二进制（推荐普通用户）

1. 打开 [Releases 页面](https://github.com/wjj481/mc-bridge-tool/releases)
2. 下载你对应平台的文件：
   - Windows 64 位：`mcbridge-windows-x64.exe`
   - macOS Intel：`mcbridge-macos-x64.dmg`
   - macOS Apple Silicon：`mcbridge-macos-arm64.dmg`
   - Linux：`mcbridge-linux-x86_64.AppImage` 或解压版 tar.gz
3. 双击运行即可，无需安装 Python 环境。

### 方式 B：从源码运行（开发者）

```bash
git clone https://github.com/wjj481/mc-bridge-tool.git
cd mc-bridge-tool
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python desktop/main.py
```

---

## 第 3 步：点击「一键部署」

第一次打开工具，主界面会提示你「尚未部署服务器」。

1. 选择一个**空文件夹**作为服务器根目录（例如 `D:\MCServer`，目录名不要有中文和空格更稳妥）。
2. 选择 Paper 版本：默认推荐 1.21.4（配 Java 21），如果你装了 Java 25 也可以选 26.x。
3. 点击 **「一键部署」**。

工具会自动完成：

1. 从 PaperMC 官方 API（`https://fill.papermc.io/v3/projects/paper`）下载最新稳定版 server jar
2. 从 GeyserMC 下载 Geyser-Spigot 2.11.3 和 Floodgate-Spigot 2.2.5 插件到 `plugins/` 目录
3. 自动生成 `server.properties`、Geyser `config.yml`、Floodgate 配置
4. 自动写 `eula.txt` 为 `eula=true`

整个过程带进度条，网络正常的话 3~10 分钟完成。

> 💡 国内用户如果下载慢，工具会自动切换到国内镜像 `https://geysermc.cn` 兜底。

---

## 第 4 步：改配置

部署完成后，工具会自动打开配置页。你可以图形化调整：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| Java 版端口 | 玩家用 Java 版客户端连接的端口 | 25565 / TCP |
| 基岩版端口 | 玩家用手机 / 主机基岩版连接的端口 | 19132 / UDP |
| 内存 Xms | 启动时初始堆内存 | 1G |
| 内存 Xmx | 最大堆内存（4G 内存的电脑建议 2G） | 2G |
| 游戏模式 | survival / creative / adventure / spectator | survival |
| 难度 | peaceful / easy / normal / hard | normal |
| 最大玩家数 | 同时在线上限 | 20 |
| MOTD | 服务器列表显示的一句话 | MC Bridge Server |
| 白名单 | 开启后只有白名单玩家能进 | 关闭 |
| 正版验证 online-mode | 正版账号才能进；离线联机建议关闭 | 开启 |

改完点「保存」。

---

## 第 5 步：开服

1. 回到主界面，点 **「启动」**。
2. 下方日志区会滚动输出启动日志。看到这一行就说明启动成功：
   ```
   [Server thread/INFO]: Done (3.123s)! For help, type "help"
   ```
3. 状态面板会显示 🟢 运行中、在线玩家 0、端口监听正常。

---

## 第 6 步：进游戏

### Java 版玩家

1. 打开 Minecraft Java 版
2. 多人游戏 → 添加服务器
3. 服务器地址填：
   - 本机测试：`localhost:25565`
   - 局域网好友：`开服电脑的局域网IP:25565`（例如 `192.168.1.10:25565`）

### 基岩版玩家（手机 / 平板 / 主机）

见 [30-connect-bedrock.md](30-connect-bedrock.md) 详细教程。

---

## 常见下一步

- 想让外网好友也能连？看 [20-network.md](20-network.md) 配端口映射
- 手机加不上服？看 [30-connect-bedrock.md](30-connect-bedrock.md)
- 碰到其他问题？看 [40-faq.md](40-faq.md)
