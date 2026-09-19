"""MC 互通管家 —— 桌面端 GUI（tkinter，全中文，零命令行）。

直接运行：
    python desktop/main.py

所有耗时操作（下载、启动、检测）都在后台线程执行，
日志与进度通过 queue 回主线程刷新，避免 UI 卡死。
"""
from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# 允许从项目根目录直接 import mcbridge
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcbridge import backup, config as cfgmod, downloader, javaenv, monitor, server  # noqa: E402


class MCBridgeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("MC 互通管家 —— Minecraft Java/基岩互通服务器管理器")
        root.geometry("960x760")
        root.minsize(880, 680)

        self.server_dir: Path | None = None
        self.mgr: server.ServerManager | None = None
        self.log_q: queue.Queue[str] = queue.Queue()
        self.progress_q: queue.Queue[tuple] = queue.Queue()
        self._poll_id = None

        self._build_ui()
        self._poll_queue()

    # ================================================================== #
    # UI 构建
    # ================================================================== #
    def _build_ui(self) -> None:
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_deploy = ttk.Frame(nb)
        self.tab_config = ttk.Frame(nb)
        self.tab_control = ttk.Frame(nb)
        self.tab_log = ttk.Frame(nb)
        self.tab_components = ttk.Frame(nb)
        self.tab_java = ttk.Frame(nb)

        nb.add(self.tab_deploy, text="① 部署")
        nb.add(self.tab_config, text="② 配置")
        nb.add(self.tab_control, text="③ 控制 / 监控")
        nb.add(self.tab_log, text="④ 实时日志")
        nb.add(self.tab_components, text="⑤ 组件 / 备份")
        nb.add(self.tab_java, text="⑥ Java 环境")

        self._build_deploy(self.tab_deploy)
        self._build_config(self.tab_config)
        self._build_control(self.tab_control)
        self._build_log(self.tab_log)
        self._build_components(self.tab_components)
        self._build_java(self.tab_java)

        # 底部状态栏
        self.status_var = tk.StringVar(value="请先选择服务器目录")
        self.status_light = tk.Label(self.root, text="●", fg="gray", font=("Arial", 14))
        self.status_light.pack(side="left", padx=10)
        ttk.Label(self.root, textvariable=self.status_var).pack(side="left", fill="x")
        self.progress = ttk.Progressbar(self.root, mode="determinate", length=260)
        self.progress.pack(side="right", padx=10)

    # ---------- ① 目录 + 一键部署 ---------- #
    def _build_deploy(self, tab: ttk.Frame) -> None:
        box = ttk.LabelFrame(tab, text="服务器目录")
        box.pack(fill="x", padx=12, pady=8)
        self.dir_var = tk.StringVar()
        ttk.Entry(box, textvariable=self.dir_var).pack(side="left", fill="x", expand=True, padx=8, pady=8)
        ttk.Button(box, text="浏览…", command=self._choose_dir).pack(side="left", padx=4)
        ttk.Button(box, text="加载该目录", command=self._load_dir).pack(side="left", padx=4)

        box2 = ttk.LabelFrame(tab, text="一键部署（自动下载 Paper + Geyser + Floodgate 并生成配置）")
        box2.pack(fill="x", padx=12, pady=8)
        row = ttk.Frame(box2)
        row.pack(fill="x", padx=8, pady=8)
        ttk.Label(row, text="Paper 版本：").pack(side="left")
        self.paper_ver_var = tk.StringVar()
        self.paper_combo = ttk.Combobox(row, textvariable=self.paper_ver_var, width=18, state="readonly")
        self.paper_combo.pack(side="left", padx=4)
        ttk.Button(row, text="刷新版本列表", command=self._refresh_versions).pack(side="left", padx=4)
        ttk.Button(row, text="🚀 一键部署", command=self._deploy).pack(side="left", padx=12)

        self.deploy_info = ttk.Label(tab, text="说明：部署后会在服务器目录生成 paper.jar、plugins/、server.properties 并自动同意 EULA。")
        self.deploy_info.pack(anchor="w", padx=16, pady=6)

    # ---------- ② 配置表单 ---------- #
    def _build_config(self, tab: ttk.Frame) -> None:
        frm = ttk.LabelFrame(tab, text="图形化配置（保存后写入 server.properties / geyser / floodgate）")
        frm.pack(fill="both", expand=True, padx=12, pady=8)
        self.cfg_vars: dict[str, tk.Variable] = {}

        def add_row(r, label, key, default):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", padx=8, pady=4)
            v: tk.Variable
            if isinstance(default, bool):
                v = tk.BooleanVar(value=default)
                ttk.Checkbutton(frm, variable=v).grid(row=r, column=1, sticky="w", padx=4)
            else:
                v = tk.StringVar(value=str(default))
                ttk.Entry(frm, textvariable=v, width=24).grid(row=r, column=1, sticky="w", padx=4)
            self.cfg_vars[key] = v

        add_row(0, "Java 端口", "java_port", 25565)
        add_row(1, "基岩端口", "bedrock_port", 19132)
        add_row(2, "正版在线模式", "online_mode", True)
        add_row(3, "启用 Floodgate（基岩离线加入）", "floodgate_enabled", True)
        add_row(4, "最小内存 XMS", "xms", "1G")
        add_row(5, "最大内存 XMX", "xmx", "2G")
        add_row(6, "最大玩家数", "max_players", 20)
        add_row(7, "白名单", "whitelist", False)
        add_row(8, "世界名", "level_name", "world")
        add_row(9, "视距", "view_distance", 10)
        add_row(10, "MOTD", "motd", "MC Bridge Server")

        ttk.Label(frm, text="难度").grid(row=0, column=2, sticky="w", padx=8)
        self.diff_var = tk.StringVar(value="normal")
        ttk.Combobox(frm, textvariable=self.diff_var, width=12, state="readonly",
                     values=["peaceful", "easy", "normal", "hard"]).grid(row=0, column=3, sticky="w")
        ttk.Label(frm, text="游戏模式").grid(row=1, column=2, sticky="w", padx=8)
        self.gm_var = tk.StringVar(value="survival")
        ttk.Combobox(frm, textvariable=self.gm_var, width=12, state="readonly",
                     values=["survival", "creative", "adventure", "spectator"]).grid(row=1, column=3, sticky="w")

        btns = ttk.Frame(tab)
        btns.pack(fill="x", padx=12, pady=6)
        ttk.Button(btns, text="从目录加载现有配置", command=self._load_form_from_dir).pack(side="left", padx=4)
        ttk.Button(btns, text="💾 保存配置", command=self._save_config).pack(side="left", padx=4)

    # ---------- ③ 控制 / 监控 ---------- #
    def _build_control(self, tab: ttk.Frame) -> None:
        btns = ttk.LabelFrame(tab, text="服务器控制")
        btns.pack(fill="x", padx=12, pady=8)
        ttk.Button(btns, text="▶ 启动", command=self._start_server).pack(side="left", padx=8, pady=8)
        ttk.Button(btns, text="■ 停止", command=self._stop_server).pack(side="left", padx=8)
        ttk.Button(btns, text="⟳ 重启", command=self._restart_server).pack(side="left", padx=8)

        mon = ttk.LabelFrame(tab, text="状态监控面板")
        mon.pack(fill="both", expand=True, padx=12, pady=8)
        self.status_labels: dict[str, tk.StringVar] = {}
        rows = ["运行状态", "在线玩家", "玩家列表", "内存占用", "Java 端口监听", "基岩端口监听"]
        for i, name in enumerate(rows):
            ttk.Label(mon, text=name + "：").grid(row=i, column=0, sticky="w", padx=8, pady=3)
            v = tk.StringVar(value="—")
            self.status_labels[name] = v
            ttk.Label(mon, textvariable=v).grid(row=i, column=1, sticky="w", padx=4)
        ttk.Button(tab, text="刷新监控", command=self._refresh_monitor).pack(anchor="w", padx=16, pady=4)
        self.monitor_timer()

    # ---------- ④ 日志 ---------- #
    def _build_log(self, tab: ttk.Frame) -> None:
        from tkinter.scrolledtext import ScrolledText
        self.log_text = ScrolledText(tab, wrap="word", state="disabled", font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=8)
        ttk.Button(bar, text="清空", command=lambda: self._append_log("")).pack(side="left", padx=4)
        self.cmd_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.cmd_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(bar, text="发送指令", command=self._send_cmd).pack(side="left", padx=4)

    # ---------- ⑤ 组件 / 备份 ---------- #
    def _build_components(self, tab: ttk.Frame) -> None:
        cmp = ttk.LabelFrame(tab, text="组件更新")
        cmp.pack(fill="x", padx=12, pady=8)
        ttk.Button(cmp, text="检查更新", command=self._check_updates).grid(row=0, column=0, padx=8, pady=6)
        self.update_vars: dict[str, tk.StringVar] = {}
        for i, comp in enumerate(["paper", "geyser", "floodgate"], start=1):
            ttk.Label(cmp, text=f"{comp}：").grid(row=i, column=0, sticky="w", padx=8)
            v = tk.StringVar(value="未检查")
            self.update_vars[comp] = v
            ttk.Label(cmp, textvariable=v).grid(row=i, column=1, sticky="w", padx=4)
            ttk.Button(cmp, text="更新", command=lambda c=comp: self._update_comp(c)).grid(row=i, column=2, padx=8)

        bk = ttk.LabelFrame(tab, text="配置备份 / 还原")
        bk.pack(fill="x", padx=12, pady=8)
        ttk.Button(bk, text="备份配置", command=self._backup).pack(side="left", padx=8, pady=8)
        ttk.Button(bk, text="还原配置", command=self._restore).pack(side="left", padx=8)

    # ---------- ⑥ Java 环境 ---------- #
    def _build_java(self, tab: ttk.Frame) -> None:
        box = ttk.LabelFrame(tab, text="Java 环境检测")
        box.pack(fill="x", padx=12, pady=8)
        ttk.Button(box, text="检测本机 Java", command=self._detect_java).pack(anchor="w", padx=8, pady=6)
        self.java_var = tk.StringVar(value="尚未检测")
        ttk.Label(box, textvariable=self.java_var, wraplength=820, justify="left").pack(anchor="w", padx=8, pady=4)
        self.java_guide = tk.Text(tab, wrap="word", height=12, state="disabled")
        self.java_guide.pack(fill="both", expand=True, padx=12, pady=6)

    # ================================================================== #
    # 交互逻辑
    # ================================================================== #
    def _choose_dir(self) -> None:
        d = filedialog.askdirectory(title="选择 Minecraft 服务器目录")
        if d:
            self.dir_var.set(d)
            self._load_dir()

    def _load_dir(self) -> None:
        d = self.dir_var.get().strip()
        if not d:
            return
        self.server_dir = Path(d)
        self.mgr = server.ServerManager(self.server_dir)
        self.mgr.on_log = lambda line: self.log_q.put(line)
        self.status_var.set(f"已加载目录：{d}")
        self._load_form_from_dir()
        self._refresh_monitor()

    def _refresh_versions(self) -> None:
        def work():
            try:
                vers = downloader.list_paper_versions()
                self.root.after(0, lambda: self._set_versions(vers))
            except Exception as e:  # noqa: BLE001
                self.root.after(0, lambda: messagebox.showerror("错误", f"获取版本失败：{e}"))
        threading.Thread(target=work, daemon=True).start()

    def _set_versions(self, vers: list[str]) -> None:
        self.paper_combo["values"] = vers
        if vers:
            self.paper_ver_var.set(vers[0])
        self.status_var.set(f"可用 Paper 版本 {len(vers)} 个")

    def _deploy(self) -> None:
        if not self.server_dir:
            messagebox.showwarning("提示", "请先选择服务器目录")
            return
        ver = self.paper_ver_var.get() or None

        def work():
            try:
                manifest = downloader.install_server(
                    self.server_dir, ver,
                    progress_cb=lambda c, t, m: self.progress_q.put((c, t, m)),
                )
                self.root.after(0, lambda: messagebox.showinfo(
                    "完成",
                    f"部署完成！\nPaper {manifest['paper']['version']}\n"
                    f"Geyser {manifest['geyser']['version']}\nFloodgate {manifest['floodgate']['version']}",
                ))
            except Exception as e:  # noqa: BLE001
                self.root.after(0, lambda: messagebox.showerror("部署失败", str(e)))
        threading.Thread(target=work, daemon=True).start()

    # ---- 配置表单 ---- #
    def _form_to_config(self) -> cfgmod.ServerConfig:
        def get(k, default):
            v = self.cfg_vars.get(k)
            return v.get() if v else default
        cfg = cfgmod.ServerConfig(
            server_dir=self.server_dir or Path("."),
            java_port=int(get("java_port", 25565)),
            bedrock_port=int(get("bedrock_port", 19132)),
            online_mode=bool(get("online_mode", True)),
            floodgate_enabled=bool(get("floodgate_enabled", True)),
            xms=str(get("xms", "1G")),
            xmx=str(get("xmx", "2G")),
            difficulty=self.diff_var.get(),
            gamemode=self.gm_var.get(),
            motd=str(get("motd", "MC Bridge Server")),
            max_players=int(get("max_players", 20)),
            whitelist=bool(get("whitelist", False)),
            level_name=str(get("level_name", "world")),
            view_distance=int(get("view_distance", 10)),
        )
        return cfg

    def _load_form_from_dir(self) -> None:
        if not self.server_dir:
            return
        try:
            c = cfgmod.load_config(self.server_dir)
        except Exception:  # noqa: BLE001
            return
        mapping = {
            "java_port": c.java_port, "bedrock_port": c.bedrock_port,
            "online_mode": c.online_mode, "floodgate_enabled": c.floodgate_enabled,
            "xms": c.xms, "xmx": c.xmx, "max_players": c.max_players,
            "whitelist": c.whitelist, "level_name": c.level_name,
            "view_distance": c.view_distance, "motd": c.motd,
        }
        for k, val in mapping.items():
            if k in self.cfg_vars:
                self.cfg_vars[k].set(val)
        self.diff_var.set(c.difficulty)
        self.gm_var.set(c.gamemode)

    def _save_config(self) -> None:
        if not self.server_dir:
            messagebox.showwarning("提示", "请先选择服务器目录")
            return
        try:
            cfgmod.save_config(self._form_to_config())
            self.status_var.set("配置已保存")
            messagebox.showinfo("完成", "配置已写入服务器目录")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("保存失败", str(e))

    # ---- 服务器控制 ---- #
    def _start_server(self) -> None:
        if not self.server_dir or not self.mgr:
            messagebox.showwarning("提示", "请先选择服务器目录")
            return
        # 先把表单配置保存，使 XMS/XMX/端口生效
        try:
            cfgmod.save_config(self._form_to_config())
        except Exception:  # noqa: BLE001
            pass

        def work():
            try:
                self.mgr.start()
                self.root.after(0, lambda: self.status_var.set("服务器已启动"))
            except Exception as e:  # noqa: BLE001
                self.root.after(0, lambda: messagebox.showerror("启动失败", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _stop_server(self) -> None:
        if self.mgr:
            threading.Thread(target=self.mgr.stop, daemon=True).start()

    def _restart_server(self) -> None:
        if self.mgr:
            def work():
                try:
                    self.mgr.restart()
                except Exception as e:  # noqa: BLE001
                    self.root.after(0, lambda: messagebox.showerror("重启失败", str(e)))
            threading.Thread(target=work, daemon=True).start()

    def _send_cmd(self) -> None:
        if self.mgr:
            try:
                self.mgr.send_command(self.cmd_var.get())
                self.cmd_var.set("")
            except Exception as e:  # noqa: BLE001
                messagebox.showwarning("无法发送", str(e))

    # ---- 监控 ---- #
    def _refresh_monitor(self) -> None:
        if not self.server_dir:
            return
        try:
            st = monitor.get_status(self.server_dir)
        except Exception:  # noqa: BLE001
            return
        self.status_labels["运行状态"].set("运行中" if st.running else "未运行")
        self.status_labels["在线玩家"].set(f"{st.players_online} / {st.players_max}")
        self.status_labels["玩家列表"].set(", ".join(st.players_list) or "（空）")
        self.status_labels["内存占用"].set(f"{st.mem_used_mb} / {st.mem_total_mb} MB")
        self.status_labels["Java 端口监听"].set("是" if st.java_port_listening else "否")
        self.status_labels["基岩端口监听"].set("是" if st.bedrock_port_listening else "否")
        self.status_light.config(fg="green" if st.running else "gray")

    def monitor_timer(self) -> None:
        self._refresh_monitor()
        self.root.after(5000, self.monitor_timer)

    # ---- 组件 / 备份 ---- #
    def _check_updates(self) -> None:
        if not self.server_dir:
            messagebox.showwarning("提示", "请先选择服务器目录")
            return

        def work():
            try:
                res = downloader.check_updates(self.server_dir)
                self.root.after(0, lambda: self._show_updates(res))
            except Exception as e:  # noqa: BLE001
                self.root.after(0, lambda: messagebox.showerror("检查失败", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _show_updates(self, res: dict) -> None:
        for comp, info in res.items():
            cur = info.get("current") or "未安装"
            latest = info.get("latest") or "?"
            flag = "可更新" if info.get("update_available") else "已是最新/未知"
            self.update_vars[comp].set(f"{cur} → {latest}（{flag}）")

    def _update_comp(self, comp: str) -> None:
        if not self.server_dir:
            messagebox.showwarning("提示", "请先选择服务器目录")
            return

        def work():
            try:
                downloader.update_component(
                    self.server_dir, comp,
                    progress_cb=lambda c, t, m: self.progress_q.put((c, t, m)),
                )
                self.root.after(0, lambda: messagebox.showinfo("完成", f"{comp} 已更新"))
            except Exception as e:  # noqa: BLE001
                self.root.after(0, lambda: messagebox.showerror("更新失败", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _backup(self) -> None:
        if not self.server_dir:
            messagebox.showwarning("提示", "请先选择服务器目录")
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".zip", filetypes=[("Zip 备份", "*.zip")],
            initialfile="mcbridge_backup.zip")
        if dest:
            backup.backup_config(self.server_dir, Path(dest))
            messagebox.showinfo("完成", "备份已保存")

    def _restore(self) -> None:
        if not self.server_dir:
            messagebox.showwarning("提示", "请先选择服务器目录")
            return
        src = filedialog.askopenfilename(filetypes=[("Zip 备份", "*.zip")])
        if src:
            backup.restore_config(Path(src), self.server_dir)
            messagebox.showinfo("完成", "配置已还原")

    # ---- Java ---- #
    def _detect_java(self) -> None:
        def work():
            try:
                javas = javaenv.detect_javas()
                self.root.after(0, lambda: self._show_java(javas))
            except Exception as e:  # noqa: BLE001
                self.root.after(0, lambda: messagebox.showerror("检测失败", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _show_java(self, javas: list[javaenv.JavaInfo]) -> None:
        if not javas:
            self.java_var.set("未检测到 Java。请按下方引导安装。")
            guide = javaenv.java_install_guide("")
        else:
            lines = [f"✅ 检测到 {len(javas)} 个 Java："]
            for j in javas:
                lines.append(f"  · {j.vendor} {j.major} 位={'64' if j.is_64bit else '32'}  路径={j.path}")
            self.java_var.set("\n".join(lines))
            guide = ""
        self.java_guide.config(state="normal")
        self.java_guide.delete("1.0", "end")
        if guide:
            self.java_guide.insert("end", guide)
        self.java_guide.config(state="disabled")

    # ---- 队列轮询（日志 / 进度） ---- #
    def _append_log(self, line: str) -> None:
        if line:
            self.log_text.config(state="normal")
            self.log_text.insert("end", line + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")

    def _poll_queue(self) -> None:
        try:
            while True:
                line = self.log_q.get_nowait()
                self._append_log(line)
        except queue.Empty:
            pass
        try:
            while True:
                cur, total, msg = self.progress_q.get_nowait()
                if total:
                    self.progress["maximum"] = total
                    self.progress["value"] = cur
                self.status_var.set(msg)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)


def run() -> None:
    root = tk.Tk()
    MCBridgeApp(root)
    root.mainloop()


if __name__ == "__main__":
    run()
