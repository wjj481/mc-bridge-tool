# 40 · 常见问题 FAQ

## 目录

- [安装与启动](#安装与启动)
- [网络与连接](#网络与连接)
- [Java 版本](#java-版本)
- [iOS / iPhone 相关](#ios--iphone--相关)
- [性能与内存](#性能与内存)
- [插件与版本](#插件与版本)
- [其他](#其他)

---

## 安装与启动

### Q：双击 exe 没反应 / 闪退？

- Windows 下先看有没有弹过「已保护你的电脑」蓝色提示，点「更多信息」→「仍要运行」。
- 如果是从源码跑，打开命令行进到目录执行 `python desktop/main.py`，看报错信息。
- 360 / 火绒等杀毒软件可能误报 PyInstaller 打的包，加白名单即可。

### Q：提示「未找到 Java」？

本工具管理的 Minecraft 服务端需要 JDK 才能跑。去 [Adoptium](https://adoptium.net/temurin/releases/) 装一个 Java 21 或 Java 25。装完重启工具，它会自动检测到。

### Q：点「一键部署」卡在下载？

- 国内网络直连 PaperMC / Geyser 官方源可能慢。工具会自动切到国内镜像 `https://geysermc.cn`，如果还是慢，挂代理或稍后重试。
- 检查磁盘空间，服务端加世界文件至少留 2GB 空闲。

### Q：启动报 `eula.txt` 没同意？

正常不会出现，本工具一键部署时会自动写 `eula=true`。如果你手动改过 eula.txt 把它改回去，内容就是一行 `eula=true`。

---

## 网络与连接

### Q：朋友连不上，我自己能连？

大概率是防火墙或端口映射问题。按这个顺序查：

1. 开服电脑防火墙放行 25565/TCP 和 19132/UDP（见 [20-network.md](20-network.md)）
2. 朋友不在同一个 Wi-Fi 的话，你要有公网 IP 并做路由器端口映射
3. 运营商给的是大内网（CGNAT）时，普通端口映射没用，要找客服要公网 IP 或用 frp

### Q：Java 版能进，手机基岩版进不去？

基岩版是 **UDP 19132**，很多人只在防火墙开了 TCP。去防火墙加一条 UDP 19132 入站规则。

### Q：手机加服要填 `IP:端口` 吗？

不需要。基岩版 Minecraft 的「添加服务器」界面分两栏：地址栏只填 IP，端口栏单独填 `19132`。不要在 IP 后面写 `:19132`。

### Q：怎么知道自己有没有公网 IP？

在开服电脑浏览器搜「我的 IP」，把看到的 IP 和路由器后台 WAN 口 IP 对比，一样就是有公网 IP。

---

## Java 版本

### Q：Paper 26.x 和 1.21.x 用哪个 Java？

| Paper 版本 | 需要的 Java |
|------------|-------------|
| 26.x | Java 25 |
| 1.21.x | Java 21 |

装错版本启动会直接报 `UnsupportedClassVersionError`。本工具会在部署前自动检测并提示。

### Q：我电脑上装了多个 Java，工具会用哪个？

工具会扫描本机所有 JDK，并根据你选的 Paper 版本推荐最匹配的那个。你也可以在配置页手动指定 `java` 可执行文件路径。

### Q：Paper 旧的 v2 API 用不了？

对，PaperMC 旧的 `api.papermc.io/v2` 已经下线（sunset）。本工具已经全部切换到新接口 `https://fill.papermc.io/v3/projects/paper`，不需要你做任何事。

---

## iOS / iPhone / iPad 相关

### ⚠️ 重要：iPhone / iPad 不能当服务器宿主

**iPhone / iPad 因 iOS 沙盒限制无法运行 JVM，不能直接当 Minecraft 服务器电脑用。**

原因：

1. **iOS 不允许任意 App 运行 JVM**。苹果的 App 沙盒机制禁止第三方进程启动 / 嵌入一个独立的 Java 虚拟机，也不允许你像 Termux 那样在手机里跑一个 Linux 终端再装 OpenJDK。
2. **Minecraft 服务端（Paper）是一个 Java 程序**，必须跑在 JVM 上。没有 JVM，就跑不起 Paper，也就跑不起 Geyser / Floodgate。
3. 越狱 iOS 理论上可以装 OpenJDK，但越狱会破坏系统安全、失去保修、无法升级官方 iOS，**强烈不建议**普通用户走这条路。

### 那我想在手机上玩怎么办？

- **用安卓手机开服**：安卓有 Termux，可以装 OpenJDK 跑 Paper。教程见 [50-android-termux.md](50-android-termux.md)。
- **用电脑开服**：Windows / macOS / Linux 任何一台平时开着的电脑都行，最省心。
- **用 iOS 当遥控器**：本工具为 iOS 设计了远程控制端，你可以在 iPhone / iPad 上远程启停、改配置、看状态。详见 [60-ios-remote.md](../docs/60-ios-remote.md) 和 [ios/remote_api_design.md](../ios/remote_api_design.md)。

> 一句话总结：**iOS 是遥控器，不是服务器。服务器跑在电脑或安卓上，iPhone 负责控制和游玩。**

### Q：iPhone 能不能装你这个 App 当客户端连服务器？

能。iPhone 上的 Minecraft 基岩版本身就是客户端，按 [30-connect-bedrock.md](30-connect-bedrock.md) 加服即可。本工具的 iOS 端是额外的「管理控制台」，和你玩游戏不冲突。

---

## 性能与内存

### Q：最多给服务器分多少内存？

不要超过你物理内存的一半。8GB 内存的电脑，Xmx 设 2G~3G；16GB 设 4G~6G。分太多会导致系统卡住，分太少会频繁 GC 卡顿。

### Q：服务器 TPS 低 / 卡顿？

- 先在 MC Bridge Tool 状态面板看 TPS，低于 15 就有明显卡顿。
- 降低 `view-distance`（视距），默认 10，调成 6~8 立竿见影。
- 减少玩家总数、装的插件数量。
- 不要把 Xmx 设得太大。

### Q：笔记本开服很快发烫？

长时间开服建议插电源、垫高散热。笔记本 CPU 散热墙会导致自动降频，TPS 掉得厉害。

---

## 插件与版本

### Q：Geyser 和 Floodgate 版本是多少？

- Geyser-Spigot：**2.11.3**
- Floodgate-Spigot：**2.2.5**

本工具一键部署时会自动拉取最新版，上面两个数字是本工具发版时的实测版本。

### Q：互通服的组合是什么？

标准互通组合：

```
Paper（Java 服务端）
├── plugins/
│   ├── Geyser-Spigot.jar    ← 让基岩版玩家连进来
│   └── floodgate-spigot.jar ← 基岩版玩家免正版验证
```

不要装成「Geyser-Standalone」，那个是脱离服务端单独跑的版本，和 Paper 插件版是两码事。本工具默认下的就是 Spigot 版。

### Q：能装别的 Bukkit/Spigot 插件吗？

能。Paper 高度兼容 Bukkit / Spigot 插件。把 `.jar` 丢进 `plugins/` 目录重启即可。

---

## 其他

### Q：存档丢了 / 怎么备份？

- 世界文件在服务器根目录的 `world/` 文件夹。
- 本工具的「备份」按钮会把整个服务器配置和世界打成 zip。
- 强烈建议开服前先备份一次，每次大版本更新前也备份一次。

### Q：怎么加 OP / 管理员？

在工具的「命令控制台」输入 `op 你的游戏名` 回车即可。

### Q：支持正版验证吗？

支持。`server.properties` 里 `online-mode=true` 就是正版验证开启。想开离线联机（非正版朋友也能进）就关掉，但要承担被人冒充用户名的风险。

### Q：本工具是免费的吗？

是，MIT 协议开源，完全免费。不接受付费、不承诺商用 / 私服运营保障，详见 README 免责声明。
