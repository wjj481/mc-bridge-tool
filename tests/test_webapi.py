"""RemoteControlServer（mcbridge.webapi）单元测试。

不连真网络：用 ephemeral 端口、临时 server_dir，monkeypatch ServerManager，
仅通过 loopback 发起本地 HTTP 请求验证路由 / 认证 / CORS / 配置往返。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pytest

from mcbridge import webapi
from mcbridge.webapi import RemoteControlServer, API_PREFIX


# --------------------------------------------------------------------------- #
# Fake ServerManager：只提供 logs 需要的接口
# --------------------------------------------------------------------------- #
class _FakeManager:
    def __init__(self, server_dir):
        self.server_dir = server_dir
        self.calls = []

    def start(self, java_path=None, jvm_extra=None):
        self.calls.append(("start", java_path, jvm_extra))

    def stop(self, timeout=30):
        self.calls.append(("stop", timeout))

    def restart(self, **kw):
        self.calls.append(("restart", kw))

    def tail_logs(self, n=200):
        return [f"line-{i}" for i in range(n)]


# --------------------------------------------------------------------------- #
# Fixture
# --------------------------------------------------------------------------- #
@pytest.fixture()
def server(tmp_path, monkeypatch):
    # 用假 ServerManager 替换真实进程管理
    monkeypatch.setattr(webapi, "ServerManager", _FakeManager)
    # 状态接口也打桩，避免真去探端口 / 读日志
    monkeypatch.setattr(webapi.monitor, "get_status", lambda d: type("S", (), {
        "running": True, "players_online": 2, "players_max": 20,
        "players_list": ["Steve", "Alex"], "mem_used_mb": 512,
        "mem_total_mb": 2048, "java_port_listening": True,
        "bedrock_port_listening": True, "tps": 20.0,
    })())

    srv = RemoteControlServer(tmp_path, host="127.0.0.1", port=0)
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _url(srv: RemoteControlServer, path: str) -> str:
    return f"http://127.0.0.1:{srv.port}{path}"


def _request(srv, method, path, body=None, token=None):
    url = _url(srv, path)
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8")), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8")), dict(e.headers)


# --------------------------------------------------------------------------- #
# 测试
# --------------------------------------------------------------------------- #
def test_health_no_auth(server):
    status, payload, headers = _request(server, "GET", f"{API_PREFIX}/health")
    assert status == 200
    assert payload["ok"] is True
    assert payload["service"] == "mcbridge-remote"
    assert payload["version"] == "1.2.0"
    assert payload["port"] == server.port
    # CORS 头必须存在
    assert headers.get("Access-Control-Allow-Origin") == "*"


def test_cors_preflight(server):
    req = urllib.request.Request(_url(server, f"{API_PREFIX}/status"), method="OPTIONS")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 204
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert "GET" in resp.headers.get("Access-Control-Allow-Methods", "")
        assert "Authorization" in resp.headers.get("Access-Control-Allow-Headers", "")


def test_pair_ok_then_token(server):
    code = server.current_code()
    assert code and len(code) == 6 and code[0] != "0"

    status, payload, _ = _request(server, "POST", f"{API_PREFIX}/pair", {"code": code})
    assert status == 200
    assert payload["ok"] is True
    token = payload["token"]
    assert len(token) >= 32

    # 带 token 访问 /status 成功
    status, payload, _ = _request(server, "GET", f"{API_PREFIX}/status", token=token)
    assert status == 200
    assert payload["running"] is True
    assert payload["players_list"] == ["Steve", "Alex"]


def test_pair_wrong_code_401(server):
    status, payload, _ = _request(server, "POST", f"{API_PREFIX}/pair", {"code": "000000"})
    assert status == 401
    assert payload["ok"] is False


def test_pair_expired_code_401(server, monkeypatch):
    # 把过期时间往回拨
    server._code_expiry = time.time() - 1
    assert server.is_code_valid(server._code) is False
    status, payload, _ = _request(server, "POST", f"{API_PREFIX}/pair", {"code": server._code})
    assert status == 401


def test_status_without_token_401(server):
    status, payload, _ = _request(server, "GET", f"{API_PREFIX}/status")
    assert status == 401


def test_status_bad_token_401(server):
    status, _, _ = _request(server, "GET", f"{API_PREFIX}/status", token="bogus")
    assert status == 401


def test_config_get_put_roundtrip(server):
    code = server.current_code()
    _, p, _ = _request(server, "POST", f"{API_PREFIX}/pair", {"code": code})
    token = p["token"]

    # GET 初始
    status, cfg, _ = _request(server, "GET", f"{API_PREFIX}/config", token=token)
    assert status == 200
    assert cfg["ok"] is True
    assert cfg["max_players"] == 20

    # PUT 部分更新（motd/max_players 会落盘 server.properties；xmx 为 JVM 参数不写回）
    status, resp, _ = _request(
        server, "PUT", f"{API_PREFIX}/config",
        {"motd": "我家的小服务器", "max_players": 10}, token=token)
    assert status == 200
    assert set(resp["updated"]) >= {"motd", "max_players"}

    # 再 GET 校验落盘
    status, cfg2, _ = _request(server, "GET", f"{API_PREFIX}/config", token=token)
    assert cfg2["motd"] == "我家的小服务器"
    assert cfg2["max_players"] == 10


def test_put_config_without_token_401(server):
    status, _, _ = _request(server, "PUT", f"{API_PREFIX}/config", {"motd": "x"})
    assert status == 401


def test_refresh_code_invalidates_old(server):
    old = server.current_code()
    server.refresh_code()
    new = server.current_code()
    assert old != new
    status, _, _ = _request(server, "POST", f"{API_PREFIX}/pair", {"code": old})
    assert status == 401


def test_logs_endpoint(server):
    code = server.current_code()
    _, p, _ = _request(server, "POST", f"{API_PREFIX}/pair", {"code": code})
    token = p["token"]
    status, payload, _ = _request(server, "GET", f"{API_PREFIX}/logs?n=5&since=0", token=token)
    assert status == 200
    assert payload["ok"] is True
    assert len(payload["lines"]) == 5
    assert payload["next"] == 5


def test_manual_approve_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(webapi, "ServerManager", _FakeManager)
    srv = RemoteControlServer(tmp_path, host="127.0.0.1", port=0, manual_approve=True)
    srv.start()
    try:
        code = srv.current_code()
        # 未批准 -> 202 等待
        status, payload, _ = _request(srv, "POST", f"{API_PREFIX}/pair", {"code": code})
        assert status == 202
        assert payload["code"] == "PENDING_APPROVAL"
        assert srv.pending_pairs == [code]

        # GUI 允许
        approved = srv.allow_next_pair()
        assert approved == code
        assert srv.pending_pairs == []

        # 再次 pair 成功
        status, payload, _ = _request(srv, "POST", f"{API_PREFIX}/pair", {"code": code})
        assert status == 200 and payload["token"]
    finally:
        srv.stop()
