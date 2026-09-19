# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for MC Bridge Tool (desktop tkinter frontend).

用法（在仓库根目录）：
    pyinstaller packaging/mcbridge.spec

产物：
    dist/MC Bridge Tool/            （onedir 模式，桌面快捷方式可直接用）
    或单文件：见 build_*.bat/sh 脚本里 --onefile 的注释。

注意：
- 入口是 desktop/main.py。
- 中文应用名："MC Bridge Tool"。
- Windows 下加 --windowed 去掉控制台黑窗；Linux/macOS 保留控制台方便看日志。
- 32 位 Windows 需要在 Python 3.10 32 位环境下打包。
"""

import sys
from pathlib import Path

block_cipher = None

# 仓库根（spec 文件在 packaging/ 下，上一级才是根）
ROOT = Path(SPECPATH).resolve().parent
ENTRY = str(ROOT / "desktop" / "main.py")

is_win = sys.platform == "win32"
is_mac = sys.platform == "darwin"
is_linux = sys.platform.startswith("linux")

a = Analysis(
    [ENTRY],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # 如果有 assets/ 下的图标/截图，打包进去
        # (str(ROOT / "assets"), "assets"),
    ],
    hiddenimports=[
        # tkinter 是标准库，PyInstaller 一般能自动识别；显式列出以防万一
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "tkinter.scrolledtext",
        # mcbridge 核心库
        "mcbridge",
        "mcbridge.config",
        "mcbridge.downloader",
        "mcbridge.server",
        "mcbridge.monitor",
        "mcbridge.javaenv",
        "mcbridge.backup",
        "mcbridge.constants",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 打包时不要把 kivy 打进去（桌面端用 tkinter）
        "kivy",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---- 单文件 vs 目录 ----
# 生产建议 onedir（启动快、兼容好）；如需单文件把下面改成 True。
ONEFILE = False

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="MC Bridge Tool",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        # Windows 下 --windowed 不弹控制台；Linux 保留控制台便于看日志
        console=not is_win,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        # icon=str(ROOT / "assets" / "icon.ico"),  # 有图标时取消注释
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="MC Bridge Tool",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=not is_win,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        # icon=str(ROOT / "assets" / "icon.ico"),
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="MC Bridge Tool",
    )

# ---- macOS 应用包 ----
if is_mac:
    app = BUNDLE(
        coll if not ONEFILE else exe,
        name="MC Bridge Tool.app",
        icon=None,  # str(ROOT / "assets" / "icon.icns") 有图标时填
        bundle_identifier="com.wjj481.mcbridge",
        info_plist={
            "CFBundleName": "MC Bridge Tool",
            "CFBundleDisplayName": "MC Bridge Tool",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
        },
    )
