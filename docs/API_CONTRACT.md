# MC Bridge Tool 核心库 API 契约（v1.0）

> 所有子代理必须严格遵守此契约。核心库 `mcbridge/` 的公开接口以此为准，
> 桌面端、Android 端、测试都按此调用。契约未覆盖的实现细节可自由发挥。

## 0. 设计原则
- 纯逻辑与平台无关代码放在 `mcbridge/`，不 import tkinter/kivy。
- 所有下载/启动/监控都要有进度回调 `progress_cb(current, total, message)`，GUI 据此刷新进度条。
- 网络请求统一带 `User-Agent: mc-bridge-tool/1.0`，超时 30s，失败重试 2 次。
- 路径全部用 `pathlib.Path`，跨平台安全。

## 1. mcbridge.config
```python
@dataclass
class ServerConfig:
    server_dir: Path                      # 服务器根目录
    java_port: int = 25565
    bedrock_port: int = 19132
    online_mode: bool = True              # 正版验证
    floodgate_enabled: bool = True       # 允许基岩版离线加入
    xms: str = "1G"
    xmx: str = "2G"
    difficulty: str = "normal"            # peaceful/easy/normal/hard
    gamemode: str = "survival"           # survival/creative/adventure/spectator
    motd: str = "MC Bridge Server"
    max_players: int = 20
    whitelist: bool = False
    level_name: str = "world"
    view_distance: int = 10

def generate_server_properties(cfg: ServerConfig, dest: Path) -> Path: ...
def generate_geyser_config(cfg: ServerConfig, dest: Path) -> Path: ...
def generate_floodgate_config(cfg: ServerConfig, dest: Path) -> Path: ...
def accept_eula(server_dir: Path) -> Path: ...          # 写 eula.txt=eula=true
def load_config(server_dir: Path) -> ServerConfig: ... # 从已有 server.properties 读回
def save_config(cfg: ServerConfig) -> None: ...         # 写回所有配置文件
```
server.properties 必须包含：server-port, online-mode, difficulty, gamemode,
motd, max-players, white-list, level-name, view-distance。

## 2. mcbridge.downloader
```python
def list_paper_versions() -> list[str]:
    """返回稳定版本号列表，如 ['26.2','26.1.2','1.21.4','1.20.6',...]，新→旧。"""

def resolve_paper(version: str | None = None) -> dict:
    """version=None 取最新稳定版。返回:
    {'version':str,'build':int,'file':str,'sha256':str,'size':int,'url':str}"""

def resolve_geyser(platform: str = "spigot") -> dict:
    """返回 {'version':str,'build':int,'file':str,'sha256':str,'size':int,'url':str}"""

def resolve_floodgate(platform: str = "spigot") -> dict: ...

def download_file(url: str, dest: Path, sha256: str | None = None,
                  progress_cb=None) -> Path:
    """流式下载；若给 sha256 则校验，不符抛 ValueError。支持断点/覆盖。"""

def install_server(server_dir: Path, paper_version: str | None = None,
                   progress_cb=None) -> dict:
    """一键部署：下载 paper 到根目录、geyser-spigot.jar 与 floodgate-spigot.jar
    到 plugins/，生成初始配置并同意 eula。返回已安装组件清单 dict。"""

def check_updates(server_dir: Path) -> dict:
    """对比已装版本与官方 latest，返回 {'paper':{'current','latest','update_available'},
    'geyser':{...},'floodgate':{...}}"""

def update_component(server_dir: Path, component: str, progress_cb=None) -> Path:
    """component in {'paper','geyser','floodgate'}，一键更新。"""
```

## 3. mcbridge.server
```python
class ServerManager:
    def __init__(self, server_dir: Path): ...
    def start(self, java_path: str | None = None, jvm_extra: list[str] | None = None) -> None:
        """启动 `java -Xms.. -Xmx.. -jar paper.jar nogui`；已运行则报错。"""
    def stop(self, timeout: int = 30) -> None: ...   # 先 stop 指令再强杀
    def restart(self, **kw) -> None: ...
    def is_running(self) -> bool: ...
    def send_command(self, cmd: str) -> None: ...    # 写进 stdin（MC RCON 之外的简易方式）
    def tail_logs(self, n: int = 200) -> list[str]: ...
    def get_log_path(self) -> Path: ...
```

## 4. mcbridge.monitor
```python
@dataclass
class ServerStatus:
    running: bool
    players_online: int
    players_max: int
    players_list: list[str]
    mem_used_mb: int
    mem_total_mb: int
    java_port_listening: bool
    bedrock_port_listening: bool
    tps: float | None = None

def get_status(server_dir: Path) -> ServerStatus: ...
def parse_players_from_log(log_text: str) -> list[str]: ...
```

## 5. mcbridge.javaenv
```python
@dataclass
class JavaInfo:
    path: str
    major: int          # 21 / 25 ...
    vendor: str
    is_64bit: bool

def detect_javas() -> list[JavaInfo]: ...
def recommend_java(paper_version: str) -> JavaInfo | None:
    """26.x -> Java 25；1.21.x -> Java 21；选最匹配的已装 JDK。"""
def java_install_guide(platform: str) -> str:
    """返回引导文本（中文），告诉用户去哪下对应 JDK。"""
```

## 6. mcbridge.backup
```python
def backup_config(server_dir: Path, dest_zip: Path) -> Path: ...
def restore_config(zip_path: Path, server_dir: Path) -> Path: ...
def list_backups(backup_dir: Path) -> list[dict]: ...
```

## 7. 入口约定
- 桌面端入口：`desktop/main.py` -> `from mcbridge.desktop_app import run; run()`
- 库内不做 GUI。所有 GUI 代码在 `desktop/` 与 `android/`。
