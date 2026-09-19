"""配置备份与还原：把关键配置打包成 zip。"""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path
from typing import List

from . import constants as C

# 需要备份的相对路径（相对于 server_dir）
_BACKUP_TARGETS = [
    C.SERVER_PROPERTIES,
    C.EULA_FILE,
    C.GEYSER_CONFIG_DIR + "/config.yml",
    C.FLOODGATE_CONFIG_DIR + "/config.yml",
    ".mcbridge_manifest.json",
]


def _collect_files(server_dir: Path) -> List[Path]:
    files: List[Path] = []
    for rel in _BACKUP_TARGETS:
        p = server_dir / rel
        if p.exists():
            files.append(p)
    return files


def backup_config(server_dir: Path, dest_zip: Path) -> Path:
    """把服务器关键配置打包到 dest_zip，返回 zip 路径。"""
    server_dir = Path(server_dir)
    dest_zip = Path(dest_zip)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    files = _collect_files(server_dir)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arcname = str(f.relative_to(server_dir))
            zf.write(f, arcname)
    return dest_zip


def restore_config(zip_path: Path, server_dir: Path) -> Path:
    """从 zip 还原配置到 server_dir，返回 server_dir。"""
    zip_path = Path(zip_path)
    server_dir = Path(server_dir)
    server_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            # 防目录穿越
            target = (server_dir / name).resolve()
            if not str(target).startswith(str(server_dir.resolve())):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(target, "wb") as dst:
                dst.write(src.read())
    return server_dir


def list_backups(backup_dir: Path) -> List[dict]:
    """列出目录下所有 .zip 备份，按时间新→旧返回元信息。"""
    backup_dir = Path(backup_dir)
    out: List[dict] = []
    if not backup_dir.exists():
        return out
    for p in sorted(backup_dir.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        out.append({
            "name": p.name,
            "path": str(p),
            "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return out
