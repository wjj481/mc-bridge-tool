"""Java 环境检测与推荐。"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class JavaInfo:
    path: str
    major: int          # 21 / 25 ...
    vendor: str
    is_64bit: bool


def _run_version(java_bin: Path) -> Optional[JavaInfo]:
    """运行 `<java> -version`，解析出版本/厂商/位数。失败返回 None。"""
    try:
        proc = subprocess.run(
            [str(java_bin), "-version"],
            capture_output=True, text=True, timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = (proc.stderr or "") + (proc.stdout or "")

    # 版本号：openjdk version "21.0.1" 或 "1.8.0_381"
    m = re.search(r'version "(\d+(?:\.\d+)*(?:_\d+)?)"', out)
    if not m:
        return None
    vstr = m.group(1)
    first = vstr.split(".")[0]
    if first == "1":  # 1.8 -> 8
        major = int(vstr.split(".")[1])
    else:
        major = int(first)

    vendor = "OpenJDK"
    if "openjdk" in out.lower():
        vendor = "OpenJDK"
    if "zulu" in out.lower():
        vendor = "Zulu"
    elif "temurin" in out.lower() or "adopt" in out.lower():
        vendor = "Adoptium Temurin"
    elif "corretto" in out.lower():
        vendor = "Amazon Corretto"
    elif "microsoft" in out.lower():
        vendor = "Microsoft Build"
    elif "oracle" in out.lower():
        vendor = "Oracle OpenJDK"

    is_64 = ("64-Bit" in out) or ("x86_64" in out) or ("amd64" in out) or ("aarch64" in out)
    return JavaInfo(path=str(java_bin), major=major, vendor=vendor, is_64bit=is_64)


def _candidate_paths() -> List[Path]:
    paths: List[Path] = []
    # PATH 中的 java
    for d in os.environ.get("PATH", "").split(os.pathsep):
        exe = "java.exe" if os.name == "nt" else "java"
        cand = Path(d) / exe
        if cand.exists():
            paths.append(cand)
    # 常见 JVM 目录
    if os.name == "nt":
        roots = [Path("C:/Program Files/Java"), Path("C:/Program Files/Eclipse Adoptium")]
        for r in roots:
            if r.exists():
                paths += list(r.glob("*/bin/java.exe"))
    else:
        for r in (Path("/usr/lib/jvm"), Path("/opt/java"), Path.home() / ".sdkman/candidates/java"):
            if r.exists():
                paths += list(r.glob("*/bin/java"))
    return paths


def detect_javas() -> List[JavaInfo]:
    """检测系统中已安装的 Java，去重后按版本新→旧返回。"""
    infos: List[JavaInfo] = []
    seen = set()
    for cand in _candidate_paths():
        try:
            resolved = str(cand.resolve())
        except OSError:
            resolved = str(cand)
        if resolved in seen:
            continue
        info = _run_version(cand)
        if info:
            seen.add(resolved)
            infos.append(info)
    infos.sort(key=lambda j: j.major, reverse=True)
    return infos


def required_major(paper_version: str) -> int:
    """根据 Paper 版本推断需要的 Java 主版本。"""
    v = str(paper_version)
    if v.startswith("26.") or v.startswith("27."):
        return 25
    if v.startswith("1.21") or v.startswith("1.20") or v.startswith("1.22"):
        return 21
    if v.startswith("1.17") or v.startswith("1.18") or v.startswith("1.19"):
        return 17
    return 17


def recommend_java(paper_version: str) -> Optional[JavaInfo]:
    """按 Paper 版本推荐最匹配的已装 JDK。"""
    need = required_major(paper_version)
    javas = detect_javas()
    if not javas:
        return None
    # 优先精确匹配主版本
    exact = [j for j in javas if j.major == need]
    if exact:
        return exact[0]
    # 其次选 >= 需求的最高版本
    newer = [j for j in javas if j.major >= need]
    if newer:
        return newer[0]
    # 否则返回最高版本（可能不够，交给 GUI 提示）
    return javas[0]


def java_install_guide(platform: str) -> str:
    """返回中文安装引导。"""
    p = (platform or sys.platform).lower()
    if "win" in p:
        sysname = "Windows"
    elif "darwin" in p or "mac" in p:
        sysname = "macOS"
    else:
        sysname = "Linux"
    return (
        f"未检测到合适的 Java（当前系统：{sysname}）。\n"
        "请按以下步骤安装：\n"
        "1. 打开 Adoptium（推荐）下载页：https://adoptium.net/temurin/releases/\n"
        "2. Paper 1.21.x 选 JDK 21；Paper 26.x 选 JDK 25。\n"
        "3. 下载对应系统的 .msi / .pkg / .tar.gz 安装包并安装。\n"
        "4. 安装时勾选“Set JAVA_HOME”与“Add to PATH”。\n"
        "5. 重启本工具后重新检测。\n"
        "提示：64 位系统请选择 64-Bit (x64/aarch64) 的 JDK。"
    )
