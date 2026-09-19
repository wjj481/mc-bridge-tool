"""服务器进程管理：用 subprocess 跨平台管理 java 进程。

启动 `java -Xms.. -Xmx.. -jar paper.jar nogui`，stdin 接收控制台指令，
stdout 由后台线程读入环形缓冲（同时可通过 on_log 回调转发给 GUI 队列）。
"""
from __future__ import annotations

import queue
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional

from . import config as cfgmod
from . import constants as C

PAPER_JAR = "paper.jar"
BUFFER_LINES = 2000


class ServerManager:
    def __init__(self, server_dir: Path):
        self.server_dir = Path(server_dir)
        self._proc: Optional[subprocess.Popen] = None
        self._buf: Deque[str] = deque(maxlen=BUFFER_LINES)
        self._buf_lock = threading.Lock()
        self._reader: Optional[threading.Thread] = None
        self.on_log: Optional[callable] = None  # callback(line: str) -> None

    # ------------------------------------------------------------------ #
    def _paper_jar(self) -> Path:
        return self.server_dir / PAPER_JAR

    def get_log_path(self) -> Path:
        return self.server_dir / C.LATEST_LOG

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------ #
    def start(self, java_path: Optional[str] = None,
              jvm_extra: Optional[List[str]] = None) -> None:
        if self.is_running():
            raise RuntimeError("服务器已在运行中")
        if not self._paper_jar().exists():
            raise FileNotFoundError(f"未找到 {self._paper_jar()}，请先一键部署")

        cfg = cfgmod.load_config(self.server_dir)
        java = java_path or "java"
        cmd = [
            java,
            f"-Xms{cfg.xms}",
            f"-Xmx{cfg.xmx}",
        ]
        if jvm_extra:
            cmd.extend(jvm_extra)
        cmd += ["-jar", self._paper_jar().name, "nogui"]

        # 跨平台隐藏控制台窗口
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):  # Windows
            creationflags = subprocess.CREATE_NO_WINDOW

        self._proc = subprocess.Popen(
            cmd,
            cwd=str(self.server_dir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            bufsize=1,
            creationflags=creationflags,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.rstrip("\n")
            with self._buf_lock:
                self._buf.append(line)
            if self.on_log:
                try:
                    self.on_log(line)
                except Exception:  # noqa: BLE001 - 回调异常不得崩读取线程
                    pass

    # ------------------------------------------------------------------ #
    def send_command(self, cmd: str) -> None:
        if not self.is_running() or self._proc is None or self._proc.stdin is None:
            raise RuntimeError("服务器未运行，无法发送指令")
        self._proc.stdin.write(cmd + "\n")
        self._proc.stdin.flush()

    def stop(self, timeout: int = 30) -> None:
        if not self.is_running() or self._proc is None:
            return
        try:
            self.send_command("stop")
        except Exception:  # noqa: BLE001
            pass
        try:
            self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    def restart(self, **kw) -> None:
        self.stop()
        self.start(**kw)

    # ------------------------------------------------------------------ #
    def tail_logs(self, n: int = 200) -> List[str]:
        """优先读 logs/latest.log，回退到内存缓冲。"""
        log = self.get_log_path()
        if log.exists():
            try:
                lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()
                return lines[-n:]
            except Exception:  # noqa: BLE001
                pass
        with self._buf_lock:
            lines = list(self._buf)
        return lines[-n:]
