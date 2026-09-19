"""局域网连接码远程控制 HTTP 服务（手机 / iPad 遥控器后端）。

设计要点：
- 仅依赖标准库（http.server / socket / json / threading / secrets），可独立复用。
- 桌面端是服务端，手机/iPad 是客户端；HTTP + JSON，token 走 Authorization 头。
- 首次配对用 6 位数字连接码（内存态，默认 5 分钟有效，重启即失效）。
- 配对成功后下发 32 字节 urlsafe 短期 token（默认 24h），后续请求带 Bearer。
- UDP 广播做局域网设备发现（固定端口 37020，每 2s 一次）。
- CORS 全开放（webui 跑在 Netlify，跨域访问 LAN API）。
- 可选「人工允许接入」：manual_approve=True 时新 pair 必须经 GUI 允许后才放行。

绑定说明：
- host=None 时自动探测本机局域网 IPv4 并只绑该网卡（不绑 0.0.0.0 暴露公网语义）；
  探测失败（如离线）则回退绑定所有网卡。
- 测试 / 显式调用可传 host="127.0.0.1"、port=0（ephemeral）。
"""
from __future__ import annotations

import json
import secrets
import socket
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import __version__
from . import config as cfgmod
from . import monitor
from .server import ServerManager

API_PREFIX = "/api/v1"
BROADCAST_PORT = 37020
TOKEN_TTL = 24 * 3600          # session token 有效期 24h
BROADCAST_INTERVAL = 2.0      # 秒


# --------------------------------------------------------------------------- #
# 局域网 IPv4 探测
# --------------------------------------------------------------------------- #
def _detect_lan_ip() -> str:
    """探测本机用于局域网通信的 IPv4。

    遍历本机主机名解析出的全部地址，排除 127.x / 169.254（链路本地）/
    疑似 docker/veth 网桥（172.16~172.31 之外的 docker 段以及常见 veth 命名
    无法从纯地址判断，这里用「默认路由出口」交叉验证），优先选 RFC1918 私网地址。
    失败时回退 UDP connect 套路；再失败返回 127.0.0.1。
    """
    candidates: List[str] = []

    # 1) UDP connect 套路：拿到默认出口网卡的 IP（不真正发包）
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        candidates.append(s.getsockname()[0])
    except OSError:
        pass
    finally:
        s.close()

    # 2) 主机名解析出的全部地址
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidates.append(info[4][0])
    except OSError:
        pass

    def _private(ip: str) -> bool:
        return (
            ip.startswith(("10.", "192.168."))
            or (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31)
        )

    for ip in candidates:
        if not ip or ip.startswith("127.") or ip.startswith("169.254."):
            continue
        if ip.startswith("172.17."):  # docker0 默认网桥
            continue
        if _private(ip):
            return ip
    # 没找到私网地址，退回第一个非回环候选
    for ip in candidates:
        if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
            return ip
    return "127.0.0.1"


# --------------------------------------------------------------------------- #
# HTTP 请求处理器
# --------------------------------------------------------------------------- #
class _Handler(BaseHTTPRequestHandler):
    server_version = f"MCBridgeRemote/{__version__}"

    # ---- 工具 ---- #
    @property
    def ctrl(self) -> "RemoteControlServer":
        return self.server.ctrl  # type: ignore[attr-defined]

    def _send_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, UnicodeDecodeError):
            return {}

    def _check_token(self) -> Optional[str]:
        hdr = self.headers.get("Authorization", "")
        if not hdr.startswith("Bearer "):
            return None
        token = hdr[7:].strip()
        return token if self.ctrl.is_token_valid(token) else None

    def _require_token(self) -> Tuple[bool, dict]:
        if self._check_token() is None:
            return False, {"ok": False, "code": "UNAUTHORIZED",
                           "message": "缺少或无效的 Bearer token"}
        return True, {}

    # ---- CORS 预检 ---- #
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    # ---- 路由 ---- #
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            if path == f"{API_PREFIX}/health":
                return self._json(200, self.ctrl.health_payload())
            if path == f"{API_PREFIX}/status":
                ok, err = self._require_token()
                if not ok:
                    return self._json(401, err)
                return self._json(200, self.ctrl.status_payload())
            if path == f"{API_PREFIX}/config":
                ok, err = self._require_token()
                if not ok:
                    return self._json(401, err)
                return self._json(200, self.ctrl.get_config_payload())
            if path == f"{API_PREFIX}/logs":
                ok, err = self._require_token()
                if not ok:
                    return self._json(401, err)
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                n = int(qs.get("n", ["200"])[0])
                since = int(qs.get("since", ["0"])[0])
                return self._json(200, self.ctrl.logs_payload(n=n, since=since))
            return self._json(404, {"ok": False, "code": "NOT_FOUND", "message": path})
        except Exception as e:  # noqa: BLE001 - 兜底，避免崩连接
            return self._json(500, {"ok": False, "code": "INTERNAL", "message": str(e)})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            if path == f"{API_PREFIX}/pair":
                body = self._read_json()
                return self.ctrl.handle_pair(body, self._json)
            if path in (f"{API_PREFIX}/start", f"{API_PREFIX}/stop",
                        f"{API_PREFIX}/restart"):
                ok, err = self._require_token()
                if not ok:
                    return self._json(401, err)
                body = self._read_json()
                action = path.rsplit("/", 1)[-1]
                return self.ctrl.handle_control(action, body, self._json)
            return self._json(404, {"ok": False, "code": "NOT_FOUND", "message": path})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"ok": False, "code": "INTERNAL", "message": str(e)})

    def do_PUT(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            if path == f"{API_PREFIX}/config":
                ok, err = self._require_token()
                if not ok:
                    return self._json(401, err)
                body = self._read_json()
                return self.ctrl.handle_put_config(body, self._json)
            return self._json(404, {"ok": False, "code": "NOT_FOUND", "message": path})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"ok": False, "code": "INTERNAL", "message": str(e)})

    def log_message(self, *args) -> None:  # 静音默认访问日志
        return


class _HTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    ctrl: "RemoteControlServer" = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# 主服务类
# --------------------------------------------------------------------------- #
class RemoteControlServer:
    """局域网远程控制 HTTP 服务。

    公开方法 / 属性（供 GUI 调用）：
      - start() / stop()
      - generate_code() / refresh_code() / is_code_valid(code)
      - allow_next_pair() / pending_pairs
      - paired_count
      - health_payload() / status_payload() / get_config_payload() / logs_payload()
      - handle_pair(body, respond) / handle_control(action, body, respond)
      - handle_put_config(body, respond)
      - is_token_valid(token)
      - url_for_code() -> 二维码目标 URL
    """

    #: 允许通过 PUT /config 更新的字段白名单（server_dir 不允许远程改）
    CONFIG_FIELDS = (
        "java_port", "bedrock_port", "online_mode", "floodgate_enabled",
        "xms", "xmx", "difficulty", "gamemode", "motd", "max_players",
        "whitelist", "level_name", "view_distance",
    )

    def __init__(self, server_dir, host: Optional[str] = None, port: int = 8765,
                 code_ttl: int = 300, manual_approve: bool = False):
        self.server_dir = Path(server_dir)
        self.lan_ip = _detect_lan_ip()
        # 显式 host 优先；否则绑探测到的 LAN IP（探测失败回退全部网卡）
        self.bind_host = host if host is not None else (
            "" if self.lan_ip.startswith("127.") else self.lan_ip)
        self.port = int(port)
        self.code_ttl = int(code_ttl)
        self.manual_approve = bool(manual_approve)

        self._code: Optional[str] = None
        self._code_expiry: float = 0.0
        self._tokens: Dict[str, float] = {}          # token -> expiry 秒
        self._pending: List[str] = []               # 等待人工批准的连接码
        self._approved: List[str] = []               # 已批准、待一次性配对的连接码

        self._mgr = ServerManager(self.server_dir)
        self._httpd: Optional[_HTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._udp_stop = threading.Event()
        self._udp_thread: Optional[threading.Thread] = None
        self._started = False

    # ================================================================== #
    # 连接码 / token 管理
    # ================================================================== #
    def generate_code(self) -> str:
        """生成 6 位数字连接码（首位非 0），写入内存并设置过期时间。"""
        first = str(secrets.choice(range(1, 10)))
        rest = "".join(str(secrets.choice(range(0, 10))) for _ in range(5))
        self._code = first + rest
        self._code_expiry = time.time() + self.code_ttl
        self._pending.clear()
        self._approved.clear()
        return self._code

    def refresh_code(self) -> str:
        """换一个新连接码（旧码立即失效）。"""
        return self.generate_code()

    def is_code_valid(self, code: str) -> bool:
        if not code or self._code is None:
            return False
        if time.time() > self._code_expiry:
            return False
        return secrets.compare_digest(str(code), self._code)

    def current_code(self) -> Optional[str]:
        """当前未过期的连接码（GUI 显示用）；过期返回 None。"""
        if self._code and time.time() <= self._code_expiry:
            return self._code
        return None

    def is_token_valid(self, token: str) -> bool:
        if not token:
            return False
        exp = self._tokens.get(token)
        if exp is None:
            return False
        if time.time() > exp:
            self._tokens.pop(token, None)
            return False
        return True

    def revoke_all_tokens(self) -> None:
        self._tokens.clear()

    @property
    def paired_count(self) -> int:
        return sum(1 for exp in self._tokens.values() if time.time() <= exp)

    @property
    def pending_pairs(self) -> List[str]:
        """等待人工批准的连接码列表（GUI 展示用）。"""
        return list(self._pending)

    def allow_next_pair(self) -> Optional[str]:
        """人工允许接入：把最早一个等待中的连接码移入「已批准」，返回它。"""
        if self._pending:
            code = self._pending.pop(0)
            if code not in self._approved:
                self._approved.append(code)
            return code
        return None

    def url_for_code(self) -> str:
        """二维码内容：http://<lan_ip>:<port>/?code=xxxxxx"""
        return f"http://{self.lan_ip}:{self.port}/?code={self.current_code() or ''}"

    # ================================================================== #
    # 端点业务逻辑
    # ================================================================== #
    def health_payload(self) -> dict:
        return {
            "ok": True,
            "service": "mcbridge-remote",
            "version": __version__,
            "lan_ip": self.lan_ip,
            "port": self.port,
            "time": int(time.time()),
        }

    def status_payload(self) -> dict:
        st = monitor.get_status(self.server_dir)
        return {
            "ok": True,
            "running": st.running,
            "players_online": st.players_online,
            "players_max": st.players_max,
            "players_list": list(st.players_list),
            "mem_used_mb": st.mem_used_mb,
            "mem_total_mb": st.mem_total_mb,
            "java_port_listening": st.java_port_listening,
            "bedrock_port_listening": st.bedrock_port_listening,
            "tps": st.tps,
        }

    def get_config_payload(self) -> dict:
        cfg = cfgmod.load_config(self.server_dir)
        data = asdict(cfg)
        data["server_dir"] = str(cfg.server_dir)
        data["ok"] = True
        return data

    def handle_pair(self, body: dict, respond) -> None:
        code = str(body.get("code", ""))
        if not self.is_code_valid(code):
            return respond(401, {"ok": False, "code": "INVALID_CODE",
                                "message": "连接码错误或已过期"})
        if self.manual_approve:
            if code in self._approved:
                self._approved.remove(code)
            else:
                if code not in self._pending:
                    self._pending.append(code)
                return respond(202, {"ok": False, "code": "PENDING_APPROVAL",
                                    "message": "等待桌面端手动允许接入"})
        token = secrets.token_urlsafe(32)
        self._tokens[token] = time.time() + TOKEN_TTL
        return respond(200, {"ok": True, "token": token})

    def handle_control(self, action: str, body: dict, respond) -> None:
        try:
            if action == "start":
                self._mgr.start(java_path=body.get("java_path"),
                                jvm_extra=body.get("jvm_extra"))
                return respond(200, {"ok": True, "message": "启动中"})
            if action == "stop":
                self._mgr.stop(timeout=int(body.get("timeout", 30)))
                return respond(200, {"ok": True, "message": "已停止"})
            if action == "restart":
                self._mgr.restart()
                return respond(200, {"ok": True, "message": "重启中"})
            return respond(404, {"ok": False, "code": "NOT_FOUND"})
        except RuntimeError as e:
            return respond(409, {"ok": False, "code": "STATE_CONFLICT", "message": str(e)})
        except FileNotFoundError as e:
            return respond(409, {"ok": False, "code": "NO_SERVER", "message": str(e)})
        except Exception as e:  # noqa: BLE001
            return respond(500, {"ok": False, "code": "INTERNAL", "message": str(e)})

    def handle_put_config(self, body: dict, respond) -> None:
        try:
            cfg = cfgmod.load_config(self.server_dir)
            updated = []
            for k in self.CONFIG_FIELDS:
                if k in body:
                    setattr(cfg, k, body[k])
                    updated.append(k)
            cfgmod.save_config(cfg)
            return respond(200, {"ok": True, "updated": updated,
                                 "message": "配置已保存，重启后生效"})
        except Exception as e:  # noqa: BLE001
            return respond(500, {"ok": False, "code": "SAVE_FAILED", "message": str(e)})

    def logs_payload(self, n: int = 200, since: int = 0) -> dict:
        n = max(1, min(int(n), 1000))
        all_lines = self._mgr.tail_logs(1000)
        start = max(0, int(since))
        lines = all_lines[start:]
        if len(lines) > n:
            lines = lines[-n:]
        # next = 客户端下次应传的 since 游标（返回段末尾之后）
        next_cursor = start + len(lines)
        return {"ok": True, "lines": lines, "next": next_cursor}

    # ================================================================== #
    # 启动 / 停止
    # ================================================================== #
    def start(self) -> None:
        """启动 HTTP 服务（daemon 线程）+ UDP 广播。幂等。"""
        if self._started:
            return
        if self._code is None:
            self.generate_code()
        self._httpd = _HTTPServer((self.bind_host, self.port), _Handler)
        self._httpd.ctrl = self
        # 记录实际端口（ephemeral port=0 时由系统分配）
        self.port = self._httpd.server_address[1]
        self._http_thread = threading.Thread(
            target=self._httpd.serve_forever, name="mcbridge-http", daemon=True)
        self._http_thread.start()
        self._udp_stop.clear()
        self._udp_thread = threading.Thread(
            target=self._broadcast_loop, name="mcbridge-udp", daemon=True)
        self._udp_thread.start()
        self._started = True

    def stop(self) -> None:
        """优雅关闭 HTTP 与 UDP 广播，清理 token。"""
        if not self._started:
            return
        self._udp_stop.set()
        if self._udp_thread is not None:
            self._udp_thread.join(timeout=BROADCAST_INTERVAL + 1)
            self._udp_thread = None
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._http_thread is not None:
            self._http_thread.join(timeout=2)
            self._http_thread = None
        self.revoke_all_tokens()
        self._started = False

    # ---- UDP 设备发现广播 ---- #
    def _broadcast_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            payload = json.dumps({
                "service": "mcbridge-remote",
                "host": self.lan_ip,
                "port": self.port,
                "version": __version__,
            }).encode("utf-8")
            while not self._udp_stop.wait(BROADCAST_INTERVAL):
                try:
                    sock.sendto(payload, ("255.255.255.255", BROADCAST_PORT))
                except OSError:
                    pass
        finally:
            sock.close()

    def __enter__(self) -> "RemoteControlServer":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
