# MC互通管家 · Android 手机端

把你的安卓手机变成一台 **Minecraft Java + 基岩互通服务器**。
零命令行：所有操作都是点按钮。

> 方案已由社区验证可行：**Termux + openjdk + Paper + Geyser + Floodgate**。
> 本目录的 APK 只是「控制面板」，真正的 Java 服务端跑在 Termux 里。

---

## 一、最终用户怎么用（点按钮流程）

1. **装 Termux**
   从 [F-Droid](https://f-droid.org/packages/com.termux/) 或 Termux 官方 GitHub
   下载安装（**不要用 Google Play 旧版**，已停止维护）。

2. **装「MC互通管家」APK**
   从本仓库 Releases 下载 `mcbridge-*-debug.apk`（CI 在 push tag 时自动产出），
   允许「安装未知来源应用」后安装。

3. **一键装环境**
   打开 App → 「环境」页 → 点「一键安装 openjdk-21」。
   （App 会在 Termux 里跑 `pkg install openjdk-21 python`；约 2~5 分钟。）
   装完点「刷新检测」，应能看到 `Java 21`。

4. **一键部署**
   「部署」页 → 选 Paper 版本（默认 `1.21.4`，配 Java 21 最稳）→ 点「一键部署」。
   自动下载 Paper、Geyser-Spigot、floodgate-spigot，并生成初始配置、同意 EULA。

5. **配置（可选）**
   「配置」页改内存 / 端口 / 难度 / MOTD，点「保存」。

6. **开服**
   「控制台」页 → 点「启动」。状态面板显示 🟢 即成功。

7. **进服**
   同一 Wi-Fi 下，用**基岩版**（手机/Win10/Xbox/Switch）：
   添加服务器 → 地址填 `手机局域网IP:19132`（例如 `192.168.1.23:19132`）。
   Java 版则连 `手机局域网IP:25565`。

> 查手机局域网 IP：Termux 里 `ip addr show wlan0`，或路由器后台。

---

## 二、目录里都有啥

| 文件 | 作用 |
|---|---|
| `main.py` | Kivy 中文 GUI，四个页签（环境/部署/配置/控制台） |
| `termux_setup.sh` | 在 Termux 里跑的引导脚本：装 openjdk-21/python、建目录、检测 Java |
| `buildozer.spec` | python-for-android / buildozer 打包配置（包名 `com.wjj481.mcbridge`） |
| `README.md` | 本文件 |

核心业务逻辑不在本目录，而在上一级 `mcbridge/`（下载 / 启停 / 监控 / 配置）。
本目录只写 GUI，不重复造轮子。

---

## 三、给开发者：本地打包 APK

> 本机不跑 buildozer（太重）；实际 APK 由 GitHub Actions 在 push tag 时自动构建。
> 真要本地打：

```bash
# 1) 装 buildozer + python-for-android
pip install buildozer cython==0.29.36

# 2) 把核心库拷到本目录（打包需要）
cd android/
cp -r ../mcbridge ./mcbridge

# 3) 打包（首次会下 Android SDK/NDK，约 10~20 分钟）
buildozer android debug
# 产物：bin/mcbridge-1.0.0-debug.apk
```

要求：Ubuntu 22.04 / 24.04，系统装 `git zip openjdk-17 autoconf libtool` 等。
CI（`.github/workflows/android.yml`）已把这些都装好了。

---

## 四、版本/Java 对应关系（重要，装错会启动失败）

| Paper 版本 | 需要的 Java |
|---|---|
| 1.20.x / 1.21.x | **Java 21**（termux `openjdk-21`，默认） |
| 26.x | **Java 25**（termux `openjdk-25`，源里有就装） |

选错版本 → 启动报 `UnsupportedClassVersionError`。换对应 JDK 即可。

---

## 五、端口

| 用途 | 端口 | 协议 |
|---|---|---|
| Java 版直连 | 25565 | TCP |
| 基岩版直连 | 19132 | UDP |

手机做服务器时，**不要在 Termux 里跑 `apt` 装的 OpenJDK 之外的东西**；
Geyser/Floodgate 是 Paper 的插件，自动放进 `plugins/`。
