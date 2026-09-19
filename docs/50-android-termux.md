# 50 · Android Termux 开服教程

在安卓手机 / 平板上，你可以通过 **Termux** 这个 Linux 终端模拟器跑 OpenJDK，进而跑 Paper + Geyser + Floodgate。手机本身就是一台小 Linux 电脑。

> 💡 这是**真正的安卓服务器宿主方案**。与之相对，iPhone 因沙盒限制做不到这一点，见 [40-faq.md](40-faq.md)。

---

## 一、准备

### 1. 安装 Termux

- **不要从 Google Play 装旧版**（已停更）。
- 推荐从 [F-Droid](https://f-droid.org/packages/com.termux/) 或 [Termux 官方 GitHub Releases](https://github.com/termux/termux-app/releases) 下载最新 APK 安装。

### 2. 硬件要求

- 安卓 8.0 以上
- 至少 4GB 内存（跑 2GB 堆的服务端要留系统余量）
- 至少 2GB 空闲存储
- 建议插着充电器，不然手机一休眠系统就会杀后台

### 3. 锁定 Termux 后台

在安卓系统设置里：

- 给 Termux 关闭「电池优化」，允许后台运行
- 最近任务界面把 Termux 下拉「锁定」
- 开发者选项里把「后台进程限制」设为「标准限制」

---

## 二、初始化 Termux

打开 Termux，依次执行：

```bash
# 包更新
pkg update && pkg upgrade -y

# 安装 OpenJDK 21（跑 1.21.x）；如果你要跑 26.x 需要自己想办法装 JDK 25
pkg install openjdk-21 -y

# 验证
java -version
# 应该看到 openjdk version "21.x.x"

# 装 wget / curl（下载文件用）
pkg install wget curl -y
```

> Termux 官方源目前主推 JDK 21。如果你必须跑 Paper 26.x（需要 Java 25），需要自行从 Adoptium 下载 aarch64 JDK 25 解压到 Termux 目录，再手动把 `JAVA_HOME` 指向它。普通玩家建议直接用 1.21.4。

---

## 三、建服务器目录

```bash
mkdir -p ~/mcserver
cd ~/mcserver
```

---

## 四、手动部署（命令行方式）

如果你只是想在手机上跑起来，不一定要装 MC Bridge Tool 的 Android 版，可以直接命令行：

### 1. 下载 Paper

```bash
# 查最新版本（Paper v3 API）
curl -s https://fill.papermc.io/v3/projects/paper | head

# 下载 1.21.4 最新构建（举例）
curl -L -o paper.jar "https://fill.papermc.io/v3/projects/paper/versions/1.21.4/builds/latest/downloads/paper"
```

### 2. 同意 EULA

```bash
echo "eula=true" > eula.txt
```

### 3. 先跑一次让它生成配置

```bash
java -Xms512M -Xmx2G -jar paper.jar nogui
```

它会生成 `server.properties` 然后退出。用 `nano server.properties` 改端口、内存等。

### 4. 下载 Geyser 和 Floodgate 到 plugins/

```bash
mkdir -p plugins
cd plugins

# Geyser-Spigot 2.11.3
curl -L -e "User-Agent: mc-bridge-tool/1.0" -o Geyser-Spigot.jar \
  "https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest/downloads/spigot"

# Floodgate-Spigot 2.2.5
curl -L -e "User-Agent: mc-bridge-tool/1.0" -o floodgate-spigot.jar \
  "https://download.geysermc.org/v2/projects/floodgate/versions/latest/builds/latest/downloads/spigot"

cd ~/mcserver
```

### 5. 启动

```bash
java -Xms512M -Xmx2G -jar paper.jar nogui
```

看到 `Done!` 就成功了。

---

## 五、用 MC Bridge Tool 的 Android 版（推荐）

如果你想用图形化按钮操作，而不是敲命令：

1. 从 [Releases](https://github.com/wjj481/mc-bridge-tool/releases) 下载 Android 版 APK（Kivy 打包）。
2. 安装后打开，它会引导你授权 Termux 环境、自动完成上面第 2~4 步。
3. 之后所有启停、配置、备份都是点按钮。

> Android 版本质上是在 Termux 里跑同一个 `mcbridge` 核心库，UI 是 Kivy 界面。

---

## 六、保持后台运行

手机锁屏一会儿系统就会杀进程。几种保活方法：

### 方法 A：Termux:Boot（推荐）

装 [Termux:Boot](https://f-droid.org/packages/com.termux.boot/) 插件，开机自动跑脚本：

```bash
mkdir -p ~/.termux/boot
nano ~/.termux/boot/start-mc.sh
```

内容：

```bash
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd ~/mcserver
java -Xms512M -Xmx2G -jar paper.jar nogui
```

加执行权限：

```bash
chmod +x ~/.termux/boot/start-mc.sh
```

### 方法 B：termux-wake-lock 手动保活

```bash
termux-wake-lock
cd ~/mcserver
java -Xms512M -Xmx2G -jar paper.jar nogui
```

`termux-wake-lock` 会阻止 CPU 休眠。Termux 进程不要从最近任务里划掉。

---

## 七、连接

- 手机自己连自己：Java 版用 `localhost:25565`，基岩版用 `localhost` 端口 `19132`。
- 同 Wi-Fi 的朋友连你手机：用手机在路由器里的局域网 IP（如 `192.168.1.20:25565`）。
- 公网朋友连：参考 [20-network.md](20-network.md) 做端口映射。

---

## 八、注意事项

- **手机发热**：长时间跑 JVM 会明显发热，建议摘壳散热，夏天不要暴晒。
- **内存紧张**：4GB 内存的手机建议 Xmx 设 1.5G 以下，不然系统会杀进程。
- **Termux 别清后台**：一旦系统把 Termux 划掉，服务器就停了。
- **存储权限**：安卓 11+ 可能要给 Termux 存存储权限，不然写不进文件。
- **ARM 架构**：手机是 aarch64，不要下成 x86 的 server jar。Paper / Geyser 都是纯 Java，跨架构无问题。

---

## 九、iOS 对比

| 能力 | Android (Termux) | iPhone / iPad (iOS) |
|------|------------------|---------------------|
| 跑 JVM / 当服务器 | ✅ 可以 | ❌ 沙盒禁止 |
| 玩基岩版客户端 | ✅ | ✅ |
| 远程控制端 | ✅ | ✅（见 [60-ios-remote.md](60-ios-remote.md)） |

如果你是 iPhone 用户，**请用一台电脑或一台安卓手机开服，iPhone 只做遥控和客户端**。
