#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MC互通管家 —— Android / 手机端 Kivy GUI。

设计说明
========
* 纯 GUI 层，所有业务逻辑复用 ``mcbridge`` 核心库（见 docs/API_CONTRACT.md）。
* 四个页面（ScreenManager 切换）：
    1. 环境   EnvScreen     —— 检测 Java、引导在 Termux 内安装 openjdk / python
    2. 部署   DeployScreen  —— 选 Paper 版本，一键下载 Paper + Geyser + Floodgate
    3. 配置   ConfigScreen  —— server.properties / Geyser / Floodgate 表单
    4. 控制台 ConsoleScreen —— 启动 / 停止 / 重启 + 状态监控 + 日志查看
* 长任务（下载、安装、启停）一律放到后台线程；回主线程刷新 UI 用
  ``Clock.schedule_once`` / ``@mainthread``，避免阻塞 UI。
* 同时兼容两种运行形态：
    - 打包成 APK（buildozer，独立 App）：通过按钮引导用户先装 Termux 与 JDK；
    - 在 Termux 里直接 ``python main.py`` 跑：检测到 ``$PREFIX`` 为 termux 时，
      「一键安装环境」按钮会真正执行 ``pkg install ...``。
"""

from __future__ import annotations

import os
import socket
import threading
from pathlib import Path
from typing import Any, Callable

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen, ScreenManager, NoTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput
from kivy.core.clipboard import Clipboard

# ---- 复用核心库（契约见 docs/API_CONTRACT.md）----
# 容错导入：核心库可能在另一个并行代理里实现中，这里把 import 包一层，
# 保证即使某个子模块暂时缺失，GUI 仍可启动并提示，而不是直接崩。
try:  # pragma: no cover - 运行期容错
    from mcbridge import constants as C
    from mcbridge.config import (
        ServerConfig,
        load_config,
        save_config,
        generate_server_properties,
        accept_eula,
    )
    from mcbridge.downloader import (
        list_paper_versions,
        install_server,
        check_updates,
    )
    from mcbridge.server import ServerManager
    from mcbridge.monitor import get_status
    from mcbridge.javaenv import detect_javas, recommend_java, java_install_guide
    _MCBRIDGE_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001
    C = None  # type: ignore[assignment]
    ServerConfig = None  # type: ignore[assignment,misc]
    load_config = save_config = None  # type: ignore[assignment]
    generate_server_properties = accept_eula = None  # type: ignore[assignment]
    list_paper_versions = install_server = check_updates = None  # type: ignore[assignment]
    ServerManager = None  # type: ignore[assignment,misc]
    get_status = None  # type: ignore[assignment]
    detect_javas = recommend_java = java_install_guide = None  # type: ignore[assignment]
    _MCBRIDGE_IMPORT_ERROR = exc


# --------------------------------------------------------------------------- #
# 环境与路径
# --------------------------------------------------------------------------- #

def _is_termux() -> bool:
    """判断当前是否跑在 Termux 环境里。"""
    prefix = os.environ.get("PREFIX", "")
    if prefix.startswith("/data/data/com.termux"):
        return True
    if Path("/data/data/com.termux/files/usr/bin/pkg").exists():
        return True
    return False


def _default_server_dir() -> Path:
    """服务器根目录：环境变量 > 家目录/mcbridge/server。"""
    base = os.environ.get("MCBRIDGE_HOME") or str(Path.home())
    return Path(base).expanduser() / "mcbridge" / "server"


SERVER_DIR: Path = _default_server_dir()
IS_TERMUX: bool = _is_termux()

# 底部导航：中文标签 -> Screen name
NAV_ITEMS: list[tuple[str, str]] = [
    ("环境", "env"),
    ("部署", "deploy"),
    ("配置", "config"),
    ("控制台", "console"),
]


# --------------------------------------------------------------------------- #
# 通用小部件
# --------------------------------------------------------------------------- #

class _BgBox(BoxLayout):
    """带浅灰背景的纵向 BoxLayout，避免默认白底刺眼。"""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.95, 0.95, 0.96, 1)
            self._rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=lambda *_: setattr(self._rect, "size", self.size),
                  pos=lambda *_: setattr(self._rect, "pos", self.pos))


def _kv_label(text: str, **kw: Any) -> Label:
    return Label(text=text, size_hint_y=None, halign="left", valign="middle",
                 markup=True, **kw)


class NavBar(BoxLayout):
    """底部四页导航。"""

    def __init__(self, sm: ScreenManager, **kwargs: Any) -> None:
        super().__init__(size_hint=(1, None), height=dp(56),
                         orientation="horizontal", **kwargs)
        for label, name in NAV_ITEMS:
            btn = Button(text=label, font_size=sp(16))
            btn.bind(on_release=lambda *_a, n=name: setattr(sm, "current", n))
            self.add_widget(btn)


# --------------------------------------------------------------------------- #
# Screen 1：环境检测与一键安装
# --------------------------------------------------------------------------- #

ENV_GUIDE = (
    "【首次使用】\n"
    "1) 安装 Termux（F-Droid / 官网下载，勿用 Google Play 旧版）；\n"
    "2) 打开 Termux，点下面「复制安装命令」，粘贴回车；\n"
    "3) 等待 pkg 安装 openjdk / python 完成；\n"
    "4) 回到本工具，下拉刷新确认 Java 版本已识别。\n\n"
    "提示：Paper 26.x 需要 openjdk-25；Paper 1.21.x 需要 openjdk-21。\n"
    "当前默认推荐 openjdk-21，对多数版本最稳。\n"
)


class EnvScreen(Screen):
    """环境检测 + Termux 引导。"""

    def __init__(self, **kw: Any) -> None:
        super().__init__(name="env", **kw)
        root = _BgBox(orientation="vertical", padding=dp(12), spacing=dp(8))

        head = Label(text="[b]① 环境检测 / 一键安装 JDK[/b]",
                     markup=True, size_hint_y=None, height=dp(36),
                     halign="left")
        root.add_widget(head)

        self.status = Label(text="尚未检测…", size_hint_y=None, height=dp(120),
                            halign="left", valign="top", markup=True)
        self.status.bind(size=lambda *_: setattr(self.status, "text_size",
                                                 self.status.size))
        root.add_widget(self.status)

        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.btn_scan = Button(text="刷新检测", background_color=(0.2, 0.5, 1, 1))
        self.btn_scan.bind(on_release=lambda *_: self._scan())
        row.add_widget(self.btn_scan)

        self.btn_install = Button(text="一键安装 openjdk-21",
                                  background_color=(0.1, 0.7, 0.3, 1))
        self.btn_install.bind(on_release=lambda *_: self._install_jdk())
        row.add_widget(self.btn_install)
        root.add_widget(row)

        row2 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.btn_copy = Button(text="复制安装命令到 Termux",
                              background_color=(0.9, 0.55, 0.1, 1))
        self.btn_copy.bind(on_release=lambda *_: self._copy_cmd())
        row2.add_widget(self.btn_copy)
        root.add_widget(row2)

        self.guide = Label(text=ENV_GUIDE, size_hint_y=None,
                          halign="left", valign="top", markup=True)
        self.guide.bind(texture_size=lambda *_: setattr(
            self.guide, "height", self.guide.texture_size[1]))
        self.guide.bind(size=lambda *_: setattr(self.guide, "text_size",
                                               self.guide.size))
        root.add_widget(self.guide)

        self.add_widget(root)
        Clock.schedule_once(lambda *_: self._scan(), 0.3)

    # -- 后台任务包装 --
    def _run(self, fn: Callable[[], str], done: Callable[[str], None]) -> None:
        def worker() -> None:
            try:
                msg = fn()
            except Exception as exc:  # noqa: BLE001
                msg = f"出错：{exc}"
            Clock.schedule_once(lambda *_: done(msg), 0)
        threading.Thread(target=worker, daemon=True).start()

    def _scan(self) -> None:
        self.status.text = "正在检测 Java…"

        def work() -> str:
            if _MCBRIDGE_IMPORT_ERROR:
                return f"核心库未就绪：{_MCBRIDGE_IMPORT_ERROR}\n请等待 mcbridge/ 完成。"
            infos = detect_javas()  # type: ignore[operator]
            if not infos:
                tip = java_install_guide("android")  # type: ignore[misc]
                return f"未检测到 Java。\n{tip}"
            lines = ["已检测到 JDK："]
            for j in infos:
                lines.append(f"  • {j.major}  ({j.vendor})\n    路径: {j.path}")
            rec = recommend_java(C.PAPER_DEFAULT_VERSION) if C else None  # type: ignore[union-attr]
            if rec:
                lines.append(f"推荐使用：Java {rec.major}")
            return "\n".join(lines)

        self._run(work, lambda msg: setattr(self.status, "text", msg))

    def _install_jdk(self) -> None:
        self.btn_install.disabled = True
        self.status.text = "正在安装 openjdk-21（首次约 2~5 分钟）…"

        def work() -> str:
            if not IS_TERMUX:
                return ("当前不是 Termux 环境，无法直接 pkg 安装。\n"
                        "请先安装 Termux，再点「复制安装命令」在 Termux 里执行。")
            import subprocess
            cmd = ["pkg", "install", "-y", "openjdk-21", "python", "termux-tools"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if r.returncode != 0:
                return f"pkg 安装失败：\n{r.stderr[-800:]}"
            return "openjdk-21 / python 安装完成，请回到「刷新检测」确认。"

        def done(msg: str) -> None:
            self.btn_install.disabled = False
            self.status.text = msg
            self._scan()

        self._run(work, done)

    @staticmethod
    def _copy_cmd() -> None:
        Clipboard.copy("pkg update && pkg install -y openjdk-21 python termux-tools")


# --------------------------------------------------------------------------- #
# Screen 2：一键部署
# --------------------------------------------------------------------------- #

class DeployScreen(Screen):
    """选 Paper 版本 + 一键安装。"""

    def __init__(self, **kw: Any) -> None:
        super().__init__(name="deploy", **kw)
        root = _BgBox(orientation="vertical", padding=dp(12), spacing=dp(8))

        root.add_widget(Label(
            text="[b]② 一键部署 Paper + Geyser + Floodgate[/b]",
            markup=True, size_hint_y=None, height=dp(36), halign="left"))

        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        row.add_widget(Label(text="Paper 版本：", halign="left"))
        self.ver_spinner = Spinner(
            text=(C.PAPER_DEFAULT_VERSION if C else "1.21.4"),  # type: ignore[union-attr]
            values=["1.21.4"],
        )
        row.add_widget(self.ver_spinner)
        root.add_widget(row)

        self.progress = ProgressBar(max=100, value=0, size_hint_y=None,
                                   height=dp(18))
        root.add_widget(self.progress)
        self.pct = Label(text="0%", size_hint_y=None, height=dp(24))
        root.add_widget(self.pct)
        self.log = Label(text="尚未开始部署", size_hint_y=None,
                         halign="left", valign="top", markup=True)
        self.log.bind(texture_size=lambda *_: setattr(
            self.log, "height", self.log.texture_size[1]))
        self.log.bind(size=lambda *_: setattr(self.log, "text_size",
                                             self.log.size))
        root.add_widget(self.log)

        row2 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.btn_versions = Button(text="拉取版本列表")
        self.btn_versions.bind(on_release=lambda *_: self._fetch_versions())
        row2.add_widget(self.btn_versions)
        self.btn_deploy = Button(text="一键部署", background_color=(0.1, 0.7, 0.3, 1))
        self.btn_deploy.bind(on_release=lambda *_: self._deploy())
        row2.add_widget(self.btn_deploy)
        root.add_widget(row2)

        self.add_widget(root)
        Clock.schedule_once(lambda *_: self._fetch_versions(), 0.3)

    # -- 进度回调：跨线程安全 --
    def _progress_cb(self, cur: int, total: int, msg: str) -> None:
        pct = int(cur * 100 / total) if total else 0

        def ui(_: Any) -> None:
            self.progress.value = pct
            self.pct.text = f"{pct}%"
            self.log.text = msg
        Clock.schedule_once(ui, 0)

    def _fetch_versions(self) -> None:
        self.log.text = "正在拉取 Paper 版本列表…"

        def work() -> list[str]:
            if _MCBRIDGE_IMPORT_ERROR or list_paper_versions is None:  # type: ignore[truthy-bool]
                return ["1.21.4"]
            return list_paper_versions()  # type: ignore[no-any-return]

        def done(vers: list[str]) -> None:
            self.ver_spinner.values = vers or ["1.21.4"]
            self.log.text = f"可用版本 {len(self.ver_spinner.values)} 个，已加载。"

        def worker() -> None:
            try:
                vers = work()
            except Exception as exc:  # noqa: BLE001
                vers = ["1.21.4"]
                Clock.schedule_once(lambda *_: setattr(
                    self.log, "text", f"拉取失败，回退默认 1.21.4：{exc}"), 0)
            Clock.schedule_once(lambda *_: done(vers), 0)
        threading.Thread(target=worker, daemon=True).start()

    def _deploy(self) -> None:
        self.btn_deploy.disabled = True
        version = self.ver_spinner.text
        self.log.text = f"开始部署 {version} …"

        def worker() -> None:
            try:
                if _MCBRIDGE_IMPORT_ERROR or install_server is None:  # type: ignore[truthy-bool]
                    raise RuntimeError("mcbridge.downloader 尚未就绪")
                SERVER_DIR.mkdir(parents=True, exist_ok=True)
                result = install_server(  # type: ignore[misc]
                    SERVER_DIR, paper_version=version,
                    progress_cb=self._progress_cb,
                )
                Clock.schedule_once(lambda *_: (
                    setattr(self.log, "text",
                            f"部署完成 ✅\n已安装：{result}"),
                    setattr(self.progress, "value", 100),
                ), 0)
            except Exception as exc:  # noqa: BLE001
                Clock.schedule_once(lambda *_: setattr(
                    self.log, "text", f"部署失败：{exc}"), 0)
            finally:
                Clock.schedule_once(lambda *_: setattr(
                    self.btn_deploy, "disabled", False), 0)

        threading.Thread(target=worker, daemon=True).start()


# --------------------------------------------------------------------------- #
# Screen 3：配置表单
# --------------------------------------------------------------------------- #

class ConfigScreen(Screen):
    """把 ServerConfig 的字段摆成表单，保存到磁盘。"""

    FIELDS: list[tuple[str, str, type]] = [
        ("java_port", "Java 端口 (TCP)", int),
        ("bedrock_port", "基岩端口 (UDP)", int),
        ("xms", "初始内存 (Xms)", str),
        ("xmx", "最大内存 (Xmx)", str),
        ("max_players", "最大玩家数", int),
        ("view_distance", "视距", int),
        ("motd", "服务器 MOTD", str),
        ("level_name", "世界名", str),
        ("difficulty", "难度 peaceful/easy/normal/hard", str),
        ("gamemode", "模式 survival/creative/adventure/spectator", str),
    ]

    def __init__(self, **kw: Any) -> None:
        super().__init__(name="config", **kw)
        root = _BgBox(orientation="vertical", padding=dp(12), spacing=dp(4))
        root.add_widget(Label(
            text="[b]③ 服务器配置[/b]", markup=True,
            size_hint_y=None, height=dp(36), halign="left"))

        scroll = ScrollView()
        form = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        form.bind(minimum_height=form.setter("height"))

        self.inputs: dict[str, TextInput] = {}
        self.switch_online: Switch | None = None
        self.switch_floodgate: Switch | None = None
        self.switch_whitelist: Switch | None = None

        cfg = self._load_or_default()
        for key, label, typ in self.FIELDS:
            row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
            row.add_widget(Label(text=label, halign="left", size_hint_x=0.5))
            ti = TextInput(multiline=False, text=str(getattr(cfg, key, "")),
                           input_filter="int" if typ is int else None)
            row.add_widget(ti)
            form.add_widget(row)
            self.inputs[key] = ti

        # 布尔开关
        for key, label, attr in [
            ("online_mode", "正版验证 online-mode", "online_mode"),
            ("floodgate_enabled", "允许基岩版离线登录", "floodgate_enabled"),
            ("whitelist", "白名单", "whitelist"),
        ]:
            row = BoxLayout(size_hint_y=None, height=dp(40))
            row.add_widget(Label(text=label, halign="left"))
            sw = Switch(active=bool(getattr(cfg, attr, False)))
            row.add_widget(sw)
            form.add_widget(row)
            if key == "online_mode":
                self.switch_online = sw
            elif key == "floodgate_enabled":
                self.switch_floodgate = sw
            else:
                self.switch_whitelist = sw

        scroll.add_widget(form)
        root.add_widget(scroll)

        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.btn_save = Button(text="保存配置", background_color=(0.2, 0.5, 1, 1))
        self.btn_save.bind(on_release=lambda *_: self._save())
        row.add_widget(self.btn_save)
        root.add_widget(row)

        self.tip = Label(text="", size_hint_y=None, height=dp(24),
                         color=(0.1, 0.6, 0.2, 1))
        root.add_widget(self.tip)
        self.add_widget(root)

    def _load_or_default(self) -> Any:
        if _MCBRIDGE_IMPORT_ERROR or load_config is None or ServerConfig is None:  # type: ignore[truthy-bool]
            return _DummyCfg()
        try:
            if SERVER_DIR.exists():
                return load_config(SERVER_DIR)  # type: ignore[misc]
        except Exception:
            pass
        return ServerConfig(server_dir=SERVER_DIR)  # type: ignore[misc,call-arg]

    def _collect(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for key, _label, typ in self.FIELDS:
            raw = self.inputs[key].text.strip()
            data[key] = typ(raw) if typ is int else raw
        data["online_mode"] = bool(self.switch_online.active)  # type: ignore[union-attr]
        data["floodgate_enabled"] = bool(self.switch_floodgate.active)  # type: ignore[union-attr]
        data["whitelist"] = bool(self.switch_whitelist.active)  # type: ignore[union-attr]
        return data

    def _save(self) -> None:
        if _MCBRIDGE_IMPORT_ERROR or ServerConfig is None or save_config is None:  # type: ignore[truthy-bool]
            self.tip.text = "核心库未就绪，无法保存"
            return
        try:
            data = self._collect()
            cfg = ServerConfig(server_dir=SERVER_DIR, **data)  # type: ignore[call-arg]
            SERVER_DIR.mkdir(parents=True, exist_ok=True)
            save_config(cfg)  # type: ignore[misc]
            accept_eula(SERVER_DIR)  # type: ignore[misc]
            self.tip.text = "✅ 已保存并同意 eula"
        except Exception as exc:  # noqa: BLE001
            self.tip.text = f"保存失败：{exc}"


class _DummyCfg:
    """mcbridge 未就绪时的占位配置。"""

    def __init__(self) -> None:
        self.java_port = 25565
        self.bedrock_port = 19132
        self.xms = "1G"
        self.xmx = "2G"
        self.max_players = 20
        self.view_distance = 10
        self.motd = "MC Bridge Server"
        self.level_name = "world"
        self.difficulty = "normal"
        self.gamemode = "survival"
        self.online_mode = True
        self.floodgate_enabled = True
        self.whitelist = False


# --------------------------------------------------------------------------- #
# Screen 4：控制台（启停 + 监控 + 日志）
# --------------------------------------------------------------------------- #

class ConsoleScreen(Screen):
    """启动 / 停止 / 重启，状态面板，日志 tail。"""

    def __init__(self, **kw: Any) -> None:
        super().__init__(name="console", **kw)
        root = _BgBox(orientation="vertical", padding=dp(12), spacing=dp(6))

        root.add_widget(Label(
            text="[b]④ 控制台 / 状态监控[/b]", markup=True,
            size_hint_y=None, height=dp(36), halign="left"))

        self.status_lbl = Label(text="未启动", size_hint_y=None, height=dp(110),
                                halign="left", valign="top", markup=True)
        self.status_lbl.bind(size=lambda *_: setattr(
            self.status_lbl, "text_size", self.status_lbl.size))
        root.add_widget(self.status_lbl)

        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.btn_start = Button(text="启动", background_color=(0.1, 0.7, 0.3, 1))
        self.btn_stop = Button(text="停止", background_color=(0.85, 0.25, 0.2, 1))
        self.btn_restart = Button(text="重启")
        self.btn_start.bind(on_release=lambda *_: self._start())
        self.btn_stop.bind(on_release=lambda *_: self._stop())
        self.btn_restart.bind(on_release=lambda *_: self._restart())
        row.add_widget(self.btn_start)
        row.add_widget(self.btn_stop)
        row.add_widget(self.btn_restart)
        root.add_widget(row)

        row2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.btn_refresh = Button(text="刷新状态")
        self.btn_refresh.bind(on_release=lambda *_: self._refresh())
        row2.add_widget(self.btn_refresh)
        root.add_widget(row2)

        root.add_widget(Label(text="日志（最近）：", halign="left",
                              size_hint_y=None, height=dp(24)))
        scroll = ScrollView(size_hint=(1, None), height=dp(260))
        self.log_lbl = Label(text="（空）", halign="left", valign="top",
                             markup=True, size_hint_y=False)
        self.log_lbl.bind(texture_size=lambda *_: setattr(
            self.log_lbl, "height", self.log_lbl.texture_size[1]))
        self.log_lbl.bind(size=lambda *_: setattr(self.log_lbl, "text_size",
                                                  self.log_lbl.size))
        scroll.add_widget(self.log_lbl)
        root.add_widget(scroll)

        self.add_widget(root)
        # 定时 3 秒刷新一次状态
        Clock.schedule_interval(lambda *_: self._refresh(), 3)

    # -- ServerManager 单例 --
    def _mgr(self) -> Any:
        if _MCBRIDGE_IMPORT_ERROR or ServerManager is None:  # type: ignore[truthy-bool]
            return None
        return ServerManager(SERVER_DIR)  # type: ignore[call-arg]

    def _start(self) -> None:
        mgr = self._mgr()
        if mgr is None:
            self.status_lbl.text = "核心库未就绪"
            return
        try:
            mgr.start()
            self.status_lbl.text = "启动指令已发送…"
        except Exception as exc:  # noqa: BLE001
            self.status_lbl.text = f"启动失败：{exc}"
        Clock.schedule_once(lambda *_: self._refresh(), 1.5)

    def _stop(self) -> None:
        mgr = self._mgr()
        if mgr is None:
            return
        try:
            mgr.stop()
            self.status_lbl.text = "已停止"
        except Exception as exc:  # noqa: BLE001
            self.status_lbl.text = f"停止失败：{exc}"
        Clock.schedule_once(lambda *_: self._refresh(), 1.0)

    def _restart(self) -> None:
        mgr = self._mgr()
        if mgr is None:
            return
        try:
            mgr.restart()
            self.status_lbl.text = "重启中…"
        except Exception as exc:  # noqa: BLE001
            self.status_lbl.text = f"重启失败：{exc}"
        Clock.schedule_once(lambda *_: self._refresh(), 3.0)

    def _refresh(self) -> None:
        if _MCBRIDGE_IMPORT_ERROR or get_status is None:  # type: ignore[truthy-bool]
            return
        try:
            st = get_status(SERVER_DIR)  # type: ignore[misc]
            text = (
                f"运行状态：{'🟢 运行中' if st.running else '🔴 已停止'}\n"
                f"玩家：{st.players_online}/{st.players_max}\n"
                f"内存：{st.mem_used_mb}/{st.mem_total_mb} MB\n"
                f"Java 端口 {25565} 监听：{st.java_port_listening}\n"
                f"基岩 端口 {19132} 监听：{st.bedrock_port_listening}\n"
            )
            if st.players_list:
                text += f"在线：{', '.join(st.players_list)}"
            self.status_lbl.text = text
            # 日志 tail
            mgr = self._mgr()
            if mgr is not None:
                lines = mgr.tail_logs(120)
                self.log_lbl.text = "\n".join(lines[-120:]) or "（无日志）"
        except Exception as exc:  # noqa: BLE001
            self.status_lbl.text = f"状态读取失败：{exc}"


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

class MCBridgeApp(App):
    """MC互通管家主 App。"""

    title = "MC互通管家"

    def build(self) -> BoxLayout:
        root = BoxLayout(orientation="vertical")
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(EnvScreen())
        sm.add_widget(DeployScreen())
        sm.add_widget(ConfigScreen())
        sm.add_widget(ConsoleScreen())
        root.add_widget(sm)
        root.add_widget(NavBar(sm))
        return root


def main() -> None:
    MCBridgeApp().run()


if __name__ == "__main__":
    main()
