"""下载与部署：Paper / Geyser / Floodgate 的版本解析、下载、SHA256 校验与一键部署。

仅依赖 requests，纯标准库 + pathlib。网络请求统一带 User-Agent、30s 超时、失败重试 2 次。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

from . import config as cfgmod
from . import constants as C

USER_AGENT = "mc-bridge-tool/1.0"
TIMEOUT = 30
RETRIES = 2
MANIFEST_NAME = ".mcbridge_manifest.json"

ProgressCb = Optional[Callable[[int, int, str], None]]


# --------------------------------------------------------------------------- #
# 网络层
# --------------------------------------------------------------------------- #
def _http_get_json(url: str, *, params: Optional[dict] = None) -> dict:
    """GET JSON，带 UA / 超时 / 重试。"""
    last_exc: Optional[Exception] = None
    for attempt in range(RETRIES + 1):
        try:
            resp = requests.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - 统一重试
            last_exc = exc
    raise RuntimeError(f"请求失败（已重试 {RETRIES} 次）: {url}: {last_exc}")


# --------------------------------------------------------------------------- #
# 版本号排序
# --------------------------------------------------------------------------- #
def _version_key(v: str) -> tuple:
    """把版本字符串转成可比较的元组。26.3 -> (26,3,0)；1.21.4 -> (1,21,4)。"""
    parts = []
    for num in re.findall(r"\d+", v):
        parts.append(int(num))
    # 归一到至少 3 段，保证 26.3 与 1.21.4 可比较
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


# --------------------------------------------------------------------------- #
# Paper
# --------------------------------------------------------------------------- #
def list_paper_versions() -> List[str]:
    """返回稳定版本号列表，新→旧。"""
    data = _http_get_json(C.PAPER_API)
    versions = list((data.get("versions") or {}).keys())
    versions.sort(key=_version_key, reverse=True)
    return versions


def _paper_build_info(version: str) -> dict:
    """取某 Paper 版本组的最新构建并规整成统一 dict。"""
    data = _http_get_json(f"{C.PAPER_API}/versions/{version}/builds/latest")
    build = int(data.get("id", 0))
    dl = (data.get("downloads") or {}).get("server:default") or {}
    # Paper v3 的 sha256 嵌在 checksums.sha256 下；兼容旧顶层字段。
    sha = (dl.get("checksums") or {}).get("sha256") or dl.get("sha256")
    return {
        "version": str(data.get("version", version)),
        "build": build,
        "channel": str(data.get("channel", "")).upper(),
        "file": dl.get("name", "paper.jar"),
        "sha256": sha,
        "size": int(dl.get("size", 0) or 0),
        "url": dl.get("url", f"{C.PAPER_API}/versions/{version}/builds/{build}/downloads/server:default"),
    }


def resolve_paper(version: Optional[str] = None) -> dict:
    """解析指定（或最新【稳定】）Paper 版本的下载信息。

    version=None 时从新到旧遍历版本组，跳过 ALPHA/RC 等非 STABLE 通道，
    第一个 STABLE 构建即为默认；若全部非稳定则退回最新一个。
    """
    if version is not None:
        return _paper_build_info(version)

    versions = list_paper_versions()
    if not versions:
        raise RuntimeError("未能获取 Paper 版本列表")

    fallback: dict | None = None
    for v in versions:
        try:
            info = _paper_build_info(v)
        except Exception:  # noqa: BLE001 - 个别版本取不到就跳过
            continue
        if fallback is None:
            fallback = info
        if info["channel"] == "STABLE":
            return info
    if fallback is not None:
        return fallback
    raise RuntimeError("未能解析 Paper 最新稳定版本")


# --------------------------------------------------------------------------- #
# Geyser / Floodgate
# --------------------------------------------------------------------------- #
def _resolve_geyser_family(api_root: str, latest_url: str, platform: str) -> dict:
    data = _http_get_json(latest_url)
    version = str(data.get("version", ""))
    build = int(data.get("build", 0))
    dl = (data.get("downloads") or {}).get(platform) or {}
    url = f"{api_root}/versions/latest/builds/latest/downloads/{platform}"
    return {
        "version": version,
        "build": build,
        "file": dl.get("name", f"{platform}.jar"),
        "sha256": dl.get("sha256"),
        "size": int(dl.get("size", 0) or 0),
        "url": dl.get("url", url),
    }


def resolve_geyser(platform: str = "spigot") -> dict:
    return _resolve_geyser_family(C.GEYSER_API, C.GEYSER_LATEST, platform)


def resolve_floodgate(platform: str = "spigot") -> dict:
    return _resolve_geyser_family(C.FLOODGATE_API, C.FLOODGATE_LATEST, platform)


# --------------------------------------------------------------------------- #
# 下载与校验
# --------------------------------------------------------------------------- #
def download_file(url: str, dest: Path, sha256: Optional[str] = None,
                  progress_cb: ProgressCb = None) -> Path:
    """流式下载到 dest；提供 sha256 则校验，不符抛 ValueError。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    last_exc: Optional[Exception] = None
    ok = False
    for attempt in range(RETRIES + 1):
        try:
            with requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                stream=True,
                timeout=TIMEOUT,
                allow_redirects=True,
            ) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0) or 0)
                hasher = hashlib.sha256()
                done = 0
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 16):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        hasher.update(chunk)
                        done += len(chunk)
                        if progress_cb:
                            progress_cb(done, total or done, f"下载 {dest.name}")
            ok = True
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if tmp.exists():
                tmp.unlink()
    if not ok:
        raise RuntimeError(f"下载失败（已重试 {RETRIES} 次）: {url}: {last_exc}")

    digest = hasher.hexdigest()
    if sha256:
        if digest.lower() != sha256.lower():
            tmp.unlink(missing_ok=True)
            raise ValueError(
                f"SHA256 校验失败: {dest.name}\n"
                f"  期望 {sha256}\n  实际 {digest}"
            )
    tmp.replace(dest)
    return dest


# --------------------------------------------------------------------------- #
# 清单（记录已装版本，用于更新检测）
# --------------------------------------------------------------------------- #
def _manifest_path(server_dir: Path) -> Path:
    return server_dir / MANIFEST_NAME


def _load_manifest(server_dir: Path) -> dict:
    p = _manifest_path(server_dir)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_manifest(server_dir: Path, manifest: dict) -> None:
    _manifest_path(server_dir).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _paper_jar(server_dir: Path) -> Path:
    return server_dir / "paper.jar"


def _geyser_jar(server_dir: Path) -> Path:
    return server_dir / C.PLUGINS_DIRNAME / "Geyser-Spigot.jar"


def _floodgate_jar(server_dir: Path) -> Path:
    return server_dir / C.PLUGINS_DIRNAME / "floodgate-spigot.jar"


# --------------------------------------------------------------------------- #
# 一键部署 / 更新
# --------------------------------------------------------------------------- #
def install_server(server_dir: Path, paper_version: Optional[str] = None,
                   progress_cb: ProgressCb = None) -> dict:
    """一键部署：下载 Paper + Geyser + Floodgate，生成配置并同意 EULA。"""
    server_dir = Path(server_dir)
    server_dir.mkdir(parents=True, exist_ok=True)
    (server_dir / C.PLUGINS_DIRNAME).mkdir(parents=True, exist_ok=True)

    def cb(step: str):
        def _inner(cur: int, total: int, msg: str) -> None:
            if progress_cb:
                progress_cb(cur, total, f"[{step}] {msg}")
        return _inner

    paper = resolve_paper(paper_version)
    download_file(paper["url"], _paper_jar(server_dir), paper["sha256"], cb("Paper"))

    geyser = resolve_geyser("spigot")
    download_file(geyser["url"], _geyser_jar(server_dir), geyser["sha256"], cb("Geyser"))

    floodgate = resolve_floodgate("spigot")
    download_file(floodgate["url"], _floodgate_jar(server_dir), floodgate["sha256"], cb("Floodgate"))

    # 生成初始配置 + 同意 eula
    cfg = cfgmod.ServerConfig(server_dir=server_dir)
    cfgmod.save_config(cfg)

    manifest = {
        "paper": {"version": paper["version"], "build": paper["build"]},
        "geyser": {"version": geyser["version"], "build": geyser["build"]},
        "floodgate": {"version": floodgate["version"], "build": floodgate["build"]},
    }
    _save_manifest(server_dir, manifest)
    return manifest


def check_updates(server_dir: Path) -> dict:
    """对比已装版本与官方 latest。"""
    manifest = _load_manifest(Path(server_dir))

    def _cmp(current: Optional[dict], latest: dict) -> dict:
        cur_ver = (current or {}).get("version")
        latest_ver = latest.get("version")
        available = bool(cur_ver) and bool(latest_ver) and str(cur_ver) != str(latest_ver)
        return {
            "current": cur_ver,
            "latest": latest_ver,
            "update_available": available,
        }

    result: Dict[str, dict] = {}
    try:
        result["paper"] = _cmp(manifest.get("paper"), resolve_paper())
    except Exception as exc:  # noqa: BLE001
        result["paper"] = {"current": (manifest.get("paper") or {}).get("version"),
                           "latest": None, "update_available": False, "error": str(exc)}
    try:
        result["geyser"] = _cmp(manifest.get("geyser"), resolve_geyser("spigot"))
    except Exception as exc:  # noqa: BLE001
        result["geyser"] = {"current": (manifest.get("geyser") or {}).get("version"),
                            "latest": None, "update_available": False, "error": str(exc)}
    try:
        result["floodgate"] = _cmp(manifest.get("floodgate"), resolve_floodgate("spigot"))
    except Exception as exc:  # noqa: BLE001
        result["floodgate"] = {"current": (manifest.get("floodgate") or {}).get("version"),
                              "latest": None, "update_available": False, "error": str(exc)}
    return result


def update_component(server_dir: Path, component: str,
                     progress_cb: ProgressCb = None) -> Path:
    """更新单个组件，返回替换后的 jar 路径。"""
    server_dir = Path(server_dir)
    manifest = _load_manifest(server_dir)

    def cb(step: str):
        def _inner(cur: int, total: int, msg: str) -> None:
            if progress_cb:
                progress_cb(cur, total, f"[更新 {step}] {msg}")
        return _inner

    if component == "paper":
        info = resolve_paper()
        dest = _paper_jar(server_dir)
        key = "paper"
    elif component == "geyser":
        info = resolve_geyser("spigot")
        dest = _geyser_jar(server_dir)
        key = "geyser"
    elif component == "floodgate":
        info = resolve_floodgate("spigot")
        dest = _floodgate_jar(server_dir)
        key = "floodgate"
    else:
        raise ValueError(f"未知组件: {component}")

    download_file(info["url"], dest, info["sha256"], cb(component))
    manifest[key] = {"version": info["version"], "build": info["build"]}
    _save_manifest(server_dir, manifest)
    return dest
