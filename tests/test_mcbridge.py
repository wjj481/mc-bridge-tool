"""mcbridge 核心库单元测试。

全部用 unittest.mock / monkeypatch 模拟网络，不真实下载大文件。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest import mock

import pytest

from mcbridge import backup, config as cfgmod, downloader, monitor


# =========================================================================== #
# 下载层 Mock
# =========================================================================== #
class _FakeJSONResp:
    def __init__(self, payload: dict):
        self._payload = payload
        self.headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeStreamResp:
    def __init__(self, content: bytes):
        self._content = content
        self.headers = {"Content-Length": str(len(content))}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1 << 16):
        data = self._content
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# --------------------------------------------------------------------------- #
# downloader
# --------------------------------------------------------------------------- #
def test_list_paper_versions_sorted(monkeypatch):
    payload = {"versions": {"1.21.4": [], "26.3": [], "26.2": [], "1.20.6": []}}
    monkeypatch.setattr(downloader.requests, "get", lambda url, **kw: _FakeJSONResp(payload))
    vers = downloader.list_paper_versions()
    assert vers == ["26.3", "26.2", "1.21.4", "1.20.6"]


def test_resolve_paper_fields(monkeypatch):
    payload = {
        "id": 123, "version": "1.21.4",
        "downloads": {"server:default": {
            "name": "paper.jar", "sha256": "abcdef", "size": 12345,
            "url": "https://example/paper.jar",
        }},
    }
    calls = {}

    def fake_get(url, **kw):
        calls["url"] = url
        return _FakeJSONResp(payload)

    monkeypatch.setattr(downloader.requests, "get", fake_get)
    info = downloader.resolve_paper("1.21.4")
    assert info["version"] == "1.21.4"
    assert info["build"] == 123
    assert info["file"] == "paper.jar"
    assert info["sha256"] == "abcdef"
    assert info["size"] == 12345
    assert info["url"] == "https://example/paper.jar"
    assert "builds/latest" in calls["url"]


def test_resolve_geyser_floodgate(monkeypatch):
    payload = {
        "version": "2.11.3", "build": 1245,
        "downloads": {"spigot": {"name": "Geyser-Spigot.jar", "sha256": "g1"}},
    }
    monkeypatch.setattr(downloader.requests, "get", lambda url, **kw: _FakeJSONResp(payload))
    g = downloader.resolve_geyser("spigot")
    assert g["version"] == "2.11.3"
    assert g["build"] == 1245
    assert g["file"] == "Geyser-Spigot.jar"
    assert g["sha256"] == "g1"

    payload2 = {
        "version": "2.2.5", "build": 141,
        "downloads": {"spigot": {"name": "floodgate-spigot.jar", "sha256": "f1"}},
    }
    monkeypatch.setattr(downloader.requests, "get", lambda url, **kw: _FakeJSONResp(payload2))
    f = downloader.resolve_floodgate("spigot")
    assert f["version"] == "2.2.5"
    assert f["build"] == 141


def test_download_file_sha256_ok(monkeypatch, tmp_path):
    content = b"FAKE-JAR-BYTES"
    digest = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(downloader.requests, "get",
                        lambda url, **kw: _FakeStreamResp(content))
    dest = tmp_path / "paper.jar"
    cb = mock.Mock()
    out = downloader.download_file("https://x/y.jar", dest, sha256=digest, progress_cb=cb)
    assert out == dest
    assert dest.read_bytes() == content
    assert cb.called  # 进度回调被调用


def test_download_file_sha256_mismatch_raises(monkeypatch, tmp_path):
    content = b"FAKE-JAR-BYTES"
    monkeypatch.setattr(downloader.requests, "get",
                        lambda url, **kw: _FakeStreamResp(content))
    dest = tmp_path / "paper.jar"
    with pytest.raises(ValueError):
        downloader.download_file("https://x/y.jar", dest, sha256="deadbeef")
    # 校验失败后临时文件应被清理
    assert not dest.exists()
    assert not (tmp_path / "paper.jar.part").exists()


def test_install_server(monkeypatch, tmp_path):
    # 三个 jar 的内容
    paper_bytes = b"paper"
    geyser_bytes = b"geyser"
    floodgate_bytes = b"floodgate"

    def fake_get(url, **kw):
        if "papermc" in url or "paper" in url:
            return _FakeStreamResp(paper_bytes)
        if "geyser" in url:
            return _FakeStreamResp(geyser_bytes)
        return _FakeStreamResp(floodgate_bytes)

    monkeypatch.setattr(downloader.requests, "get", fake_get)

    # resolve_* 返回
    paper_info = {"version": "1.21.4", "build": 1, "file": "paper.jar",
                  "sha256": hashlib.sha256(paper_bytes).hexdigest(), "size": 5,
                  "url": "https://example/paper.jar"}
    geyser_info = {"version": "2.11.3", "build": 1245, "file": "Geyser-Spigot.jar",
                   "sha256": hashlib.sha256(geyser_bytes).hexdigest(), "size": 6,
                   "url": "https://example/geyser.jar"}
    floodgate_info = {"version": "2.2.5", "build": 141, "file": "floodgate-spigot.jar",
                      "sha256": hashlib.sha256(floodgate_bytes).hexdigest(), "size": 9,
                      "url": "https://example/floodgate.jar"}

    monkeypatch.setattr(downloader, "resolve_paper", lambda v=None: paper_info)
    monkeypatch.setattr(downloader, "resolve_geyser", lambda p="spigot": geyser_info)
    monkeypatch.setattr(downloader, "resolve_floodgate", lambda p="spigot": floodgate_info)

    manifest = downloader.install_server(tmp_path, "1.21.4")
    assert (tmp_path / "paper.jar").exists()
    assert (tmp_path / "plugins" / "Geyser-Spigot.jar").exists()
    assert (tmp_path / "plugins" / "floodgate-spigot.jar").exists()
    assert (tmp_path / "eula.txt").read_text(encoding="utf-8").find("eula=true") >= 0
    assert (tmp_path / "server.properties").exists()
    assert manifest["paper"]["version"] == "1.21.4"
    assert manifest["geyser"]["version"] == "2.11.3"
    assert manifest["floodgate"]["version"] == "2.2.5"


def test_check_updates(monkeypatch, tmp_path):
    manifest = {"paper": {"version": "1.21.3", "build": 1},
                "geyser": {"version": "2.11.3", "build": 1245},
                "floodgate": {"version": "2.2.5", "build": 141}}
    (tmp_path / ".mcbridge_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(downloader, "resolve_paper",
                        lambda v=None: {"version": "1.21.4", "build": 2, "file": "p",
                                        "sha256": None, "size": 0, "url": "u"})
    monkeypatch.setattr(downloader, "resolve_geyser",
                        lambda p="spigot": {"version": "2.11.3", "build": 1245, "file": "g",
                                           "sha256": None, "size": 0, "url": "u"})
    monkeypatch.setattr(downloader, "resolve_floodgate",
                        lambda p="spigot": {"version": "2.2.5", "build": 141, "file": "f",
                                            "sha256": None, "size": 0, "url": "u"})

    res = downloader.check_updates(tmp_path)
    assert res["paper"]["current"] == "1.21.3"
    assert res["paper"]["latest"] == "1.21.4"
    assert res["paper"]["update_available"] is True
    assert res["geyser"]["update_available"] is False


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def test_server_properties_contents(tmp_path):
    cfg = cfgmod.ServerConfig(server_dir=tmp_path, java_port=25565, max_players=30,
                              difficulty="hard", gamemode="creative", whitelist=True)
    p = cfgmod.generate_server_properties(cfg, tmp_path / "server.properties")
    text = p.read_text(encoding="utf-8")
    for key in ("server-port", "online-mode", "difficulty", "gamemode",
                "motd", "max-players", "white-list", "level-name", "view-distance"):
        assert key in text, f"缺少 {key}"
    assert "server-port=25565" in text
    assert "max-players=30" in text
    assert "difficulty=hard" in text
    assert "gamemode=creative" in text
    assert "white-list=true" in text


def test_geyser_and_floodgate_config(tmp_path):
    cfg = cfgmod.ServerConfig(server_dir=tmp_path, java_port=25565,
                              bedrock_port=19132, floodgate_enabled=True)
    g = cfgmod.generate_geyser_config(cfg, tmp_path / "g.yml")
    f = cfgmod.generate_floodgate_config(cfg, tmp_path / "f.yml")
    gt = g.read_text(encoding="utf-8")
    ft = f.read_text(encoding="utf-8")
    assert "19132" in gt
    assert "25565" in gt
    assert "auth-type: floodgate" in gt
    assert "key-file-name" in ft


def test_accept_eula(tmp_path):
    p = cfgmod.accept_eula(tmp_path)
    assert p.read_text(encoding="utf-8").find("eula=true") >= 0


def test_load_save_roundtrip(tmp_path):
    cfg = cfgmod.ServerConfig(server_dir=tmp_path, java_port=26000, max_players=50,
                              difficulty="easy", gamemode="adventure", motd="Hello Bridge",
                              whitelist=True)
    cfgmod.save_config(cfg)
    back = cfgmod.load_config(tmp_path)
    assert back.java_port == 26000
    assert back.max_players == 50
    assert back.difficulty == "easy"
    assert back.gamemode == "adventure"
    assert back.motd == "Hello Bridge"
    assert back.whitelist is True


# --------------------------------------------------------------------------- #
# monitor
# --------------------------------------------------------------------------- #
SAMPLE_LOG = """[12:00:00] [Server thread/INFO]: Starting minecraft server version 1.21.4
[12:00:01] [Server thread/INFO]: Done (3.2s)! For help, type "help"
[12:01:00] [Server thread/INFO]: Steve joined the game
[12:01:05] [Server thread/INFO]: Alex joined the game
[12:02:00] [Server thread/INFO]: Notch joined the game
[12:03:00] [Server thread/INFO]: There are 3 of a max of 20 players online: Steve, Alex, Notch
"""


def test_parse_players_from_log():
    players = monitor.parse_players_from_log(SAMPLE_LOG)
    assert players == ["Steve", "Alex", "Notch"]


def test_parse_players_join_leave_fallback():
    log = """
[00:00] A joined the game
[00:01] B joined the game
[00:02] A left the game
"""
    players = monitor.parse_players_from_log(log)
    assert players == ["B"]


def test_get_status_no_server(tmp_path):
    # 没有日志文件、端口未监听 -> 返回安全的全 False 状态
    st = monitor.get_status(tmp_path)
    assert st.running is False
    assert st.players_list == []
    assert st.java_port_listening is False


def test_parse_xmx():
    assert monitor._parse_xmx_mb("2G") == 2048
    assert monitor._parse_xmx_mb("1024M") == 1024


# --------------------------------------------------------------------------- #
# backup
# --------------------------------------------------------------------------- #
def test_backup_restore_roundtrip(tmp_path):
    src = tmp_path / "server"
    src.mkdir()
    (src / "server.properties").write_text("server-port=25565\n", encoding="utf-8")
    (src / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    (src / "plugins").mkdir()
    (src / "plugins" / "Geyser-Spigot").mkdir()
    (src / "plugins" / "Geyser-Spigot" / "config.yml").write_text("bedrock:\n  port: 19132\n", encoding="utf-8")

    zip_path = tmp_path / "backups" / "b1.zip"
    backup.backup_config(src, zip_path)
    assert zip_path.exists()

    dest = tmp_path / "restored"
    backup.restore_config(zip_path, dest)
    assert (dest / "server.properties").read_text(encoding="utf-8") == "server-port=25565\n"
    assert (dest / "eula.txt").read_text(encoding="utf-8") == "eula=true\n"
    assert "19132" in (dest / "plugins" / "Geyser-Spigot" / "config.yml").read_text(encoding="utf-8")


def test_list_backups(tmp_path):
    bd = tmp_path / "backs"
    bd.mkdir()
    (bd / "a.zip").write_text("x", encoding="utf-8")
    (bd / "b.zip").write_text("yy", encoding="utf-8")
    items = backup.list_backups(bd)
    assert len(items) == 2
    assert {i["name"] for i in items} == {"a.zip", "b.zip"}
    assert backup.list_backups(tmp_path / "nonexistent") == []
