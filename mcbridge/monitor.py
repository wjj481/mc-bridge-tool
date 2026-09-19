"""服务器状态监控：从 logs/latest.log 解析在线玩家、端口监听、内存占用。"""
from __future__ import annotations

import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from . import config as cfgmod
from . import constants as C


@dataclass
class ServerStatus:
    running: bool
    players_online: int
    players_max: int
    players_list: List[str]
    mem_used_mb: int
    mem_total_mb: int
    java_port_listening: bool
    bedrock_port_listening: bool
    tps: Optional[float] = None


# --------------------------------------------------------------------------- #
# 日志解析
# --------------------------------------------------------------------------- #
# 形如：There are 3 of a max of 20 players online: Steve, Alex, Notch
_ONLINE_RE = re.compile(
    r"There are (?P<online>\d+) (?:of|out of) (?:a max of |max is )?"
    r"(?P<max>\d+) players?(?: online)?:?(?P<list>[^\n]*)",
    re.IGNORECASE,
)
_JOIN_RE = re.compile(r"\b(?P<name>[A-Za-z0-9_]{1,16}) joined the game")
_LEAVE_RE = re.compile(r"\b(?P<name>[A-Za-z0-9_]{1,16}) left the game")


def parse_players_from_log(log_text: str) -> List[str]:
    """从日志文本解析当前在线玩家名单。

    优先使用 “There are N ... players online: a, b, c” 这种权威行；
    若无，则根据 join/leave 事件推导。
    """
    # 1) 权威行
    matches = list(_ONLINE_RE.finditer(log_text))
    if matches:
        last = matches[-1]
        raw = last.group("list") or ""
        raw = raw.strip().strip(":").strip()
        if not raw:
            return []
        names = [n.strip() for n in raw.split(",")]
        return [n for n in names if n]

    # 2) 回退：根据 join / leave 事件推导
    online = set()
    for line in log_text.splitlines():
        j = _JOIN_RE.search(line)
        if j:
            online.add(j.group("name"))
            continue
        lv = _LEAVE_RE.search(line)
        if lv:
            online.discard(lv.group("name"))
    return sorted(online)


def _parse_online_count(log_text: str) -> tuple[Optional[int], int]:
    """返回 (online_count, max_count)；未知则 None。"""
    matches = list(_ONLINE_RE.finditer(log_text))
    if matches:
        last = matches[-1]
        return int(last.group("online")), int(last.group("max"))
    return None, 0


# --------------------------------------------------------------------------- #
# 端口监听探测（模块级函数，便于测试 monkeypatch）
# --------------------------------------------------------------------------- #
def _tcp_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _udp_listening(port: int, host: str = "127.0.0.1") -> bool:
    """UDP 无法可靠探活；仅作粗略判断。真正依据来自 Geyser 启动日志。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(0.4)
            s.connect((host, int(port)))
            return True  # 本地能建立路由/绑定即视为可能在监听
        finally:
            s.close()
    except OSError:
        return False


def _bedrock_started_in_log(log_text: str, port: int) -> bool:
    patterns = (
        re.compile(rf"bedrock.*{re.escape(str(port))}", re.IGNORECASE),
        re.compile(rf"Geyser.*started", re.IGNORECASE),
        re.compile(rf"Started Geyser", re.IGNORECASE),
    )
    return any(p.search(log_text) for p in patterns)


def _parse_xmx_mb(xmx: str) -> int:
    """把 '2G' / '1024M' 转成 MB。"""
    m = re.match(r"^\s*([\d.]+)\s*([gmg])?b?\s*$", xmx, re.IGNORECASE)
    if not m:
        return 0
    val = float(m.group(1))
    unit = (m.group(2) or "M").upper()
    if unit == "G":
        return int(val * 1024)
    return int(val)


def _parse_mem_used(log_text: str) -> int:
    """尽力从日志解析已用内存（MB），找不到返回 0。"""
    m = re.search(r"Used Memory:?\s*([\d.]+)\s*(MB|MiB|GB|G)", log_text, re.IGNORECASE)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2).upper()
    if unit.startswith("G"):
        return int(val * 1024)
    return int(val)


# --------------------------------------------------------------------------- #
# 主入口
# --------------------------------------------------------------------------- #
def get_status(server_dir: Path) -> ServerStatus:
    server_dir = Path(server_dir)
    log_path = server_dir / C.LATEST_LOG
    log_text = ""
    if log_path.exists():
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            log_text = ""

    cfg = cfgmod.load_config(server_dir)
    players_list = parse_players_from_log(log_text)
    online_cnt, max_cnt = _parse_online_count(log_text)
    players_online = online_cnt if online_cnt is not None else len(players_list)
    players_max = max_cnt if max_cnt else int(cfg.max_players)

    java_listening = _tcp_listening(cfg.java_port)
    bedrock_listening = _bedrock_started_in_log(log_text, cfg.bedrock_port) or \
        _udp_listening(cfg.bedrock_port)

    mem_total = _parse_xmx_mb(cfg.xmx)
    mem_used = _parse_mem_used(log_text)

    return ServerStatus(
        running=java_listening,
        players_online=players_online,
        players_max=players_max,
        players_list=players_list,
        mem_used_mb=mem_used,
        mem_total_mb=mem_total,
        java_port_listening=java_listening,
        bedrock_port_listening=bedrock_listening,
        tps=None,
    )
