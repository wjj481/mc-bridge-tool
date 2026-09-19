"""常量与已验证的下载源（2026-09-19 实测可用）。

注意：
- PaperMC 旧 v2 API(api.papermc.io/v2) 已下线(sunset)，新接口为 fill.papermc.io/v3。
- Geyser / Floodgate 仍走 download.geysermc.org/v2。
"""

# ---- 端口约定 ----
JAVA_DEFAULT_PORT = 25565      # Java 版 TCP
BEDROCK_DEFAULT_PORT = 19132    # 基岩版 UDP

# ---- PaperMC（fill v3）----
PAPER_API = "https://fill.papermc.io/v3/projects/paper"
# 取最新稳定版本号：GET {PAPER_API} -> {"versions": {"26.3":[...], "26.2":[...], ...}}
# 取某版本最新构建：GET {PAPER_API}/versions/<ver>/builds/latest
#   -> {"id":build, "channel":"STABLE",
#       "downloads":{"server:default":{"name":..,"sha256":..,"size":..,"url":..}}}
# 注意：Paper 26.x 需要 Java 25；1.21.x 需要 Java 21。
PAPER_DEFAULT_VERSION = "1.21.4"   # 默认选对 Java 21 友好、社区稳定的版本；用户可在界面改

# ---- Geyser ----
GEYSER_API = "https://download.geysermc.org/v2/projects/geyser"
GEYSER_LATEST = f"{GEYSER_API}/versions/latest/builds/latest"
# GET GEYSER_LATEST -> {"version","build", downloads:{spigot/standalone/...:{name,sha256}}}
# 下载：GET {GEYSER_API}/versions/latest/builds/latest/downloads/spigot
# 当前实测：2.11.3 (build 1245, 2026-09-17)

# ---- Floodgate ----
FLOODGATE_API = "https://download.geysermc.org/v2/projects/floodgate"
FLOODGATE_LATEST = f"{FLOODGATE_API}/versions/latest/builds/latest"
# 下载：GET {FLOODGATE_API}/versions/latest/builds/latest/downloads/spigot
# 当前实测：2.2.5 (build 141)

# ---- 目录约定（服务器根目录下）----
PLUGINS_DIRNAME = "plugins"
GEYSER_CONFIG_DIR = "plugins/Geyser-Spigot"
FLOODGATE_CONFIG_DIR = "plugins/floodgate"
SERVER_PROPERTIES = "server.properties"
EULA_FILE = "eula.txt"
LOGS_DIR = "logs"
LATEST_LOG = "logs/latest.log"

# 中文镜像备用源（主源失败时兜底，由 downloader 自动切换）
GEYSER_CN_MIRROR = "https://geysermc.cn"

# ---- JVM 默认 ----
DEFAULT_XMS = "1G"
DEFAULT_XMX = "2G"

# ---- 项目元信息（GitHub）----
GITHUB_OWNER = "wjj481"
GITHUB_REPO = "mc-bridge-tool"
GITHUB_SSH = f"git@github.com:{GITHUB_OWNER}/{GITHUB_REPO}.git"
