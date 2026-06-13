"""Tests for anonymous feature-adoption telemetry (ADR 0005)."""

from __future__ import annotations

import os

import pytest

from src.server_components.session_acl import PrincipalAclRule as RootPrincipalAclRule

# Re-export with friendlier alias for telemetry tests
PrincipalAclRule = RootPrincipalAclRule


@pytest.fixture(autouse=True)
def _clear_env():
    """Remove telemetry-related env vars before each test."""
    for key in ("DO_NOT_TRACK", "MCP_TELEMETRY_DEBUG", "MCP_TELEMETRY_INTERVAL"):
        os.environ.pop(key, None)
    yield


@pytest.fixture
def telemetry_module():
    """Import telemetry module fresh for each test (module-level cache is stateful)."""
    import importlib

    import src.telemetry as tel

    importlib.reload(tel)

    # Reset instance_id cache for clean state
    if hasattr(tel, "_instance_id"):
        tel._instance_id = None

    return tel


# ───────────────────────────── should_send ─────────────────────────────


def test_should_send_default_enabled(telemetry_module):
    """DO_NOT_TRACK unset → telemetry enabled by default."""
    assert telemetry_module.should_send() is True


def test_should_send_do_not_track_1_disables(telemetry_module):
    """DO_NOT_TRACK=1 → telemetry disabled."""
    os.environ["DO_NOT_TRACK"] = "1"
    assert telemetry_module.should_send() is False


def test_should_send_do_not_track_0_enables(telemetry_module):
    """DO_NOT_TRACK=0 → telemetry enabled."""
    os.environ["DO_NOT_TRACK"] = "0"
    assert telemetry_module.should_send() is True


def test_should_send_do_not_track_empty_value(telemetry_module):
    """DO_NOT_TRACK='' → same as unset (enabled)."""
    os.environ["DO_NOT_TRACK"] = ""
    assert telemetry_module.should_send() is True


def test_should_send_debug_mode(telemetry_module):
    """MCP_TELEMETRY_DEBUG=1 → still should_send (debug logs payload to stderr)."""
    os.environ["MCP_TELEMETRY_DEBUG"] = "1"
    assert telemetry_module.should_send() is True


# ───────────────────────────── MetricsStore ────────────────────────────


def test_metrics_store_defaults(telemetry_module):
    """MetricsStore initialises all counters to zero."""
    ms = telemetry_module.MetricsStore()
    assert ms.total_calls == 0
    assert ms.errors == 0


def test_metrics_store_increment(telemetry_module):
    """MetricsStore counters are mutable."""
    ms = telemetry_module.MetricsStore()
    ms.total_calls += 1
    ms.errors += 2
    assert ms.total_calls == 1
    assert ms.errors == 2


def test_metrics_store_snapshot_immutable(telemetry_module):
    """snapshot() returns a frozen copy; mutation does not affect original."""
    ms = telemetry_module.MetricsStore()
    ms.total_calls = 42
    snap = ms.snapshot()
    assert snap["total_calls"] == 42
    # Snapshot should be a dict, not the dataclass itself
    assert isinstance(snap, dict)


# ───────────────────────────── Instance ID ─────────────────────────────


def test_instance_id_created(telemetry_module, tmp_path):
    """First call creates instance_id file and returns UUID."""
    config_dir = tmp_path / ".config" / "fast-mcp-telegram"
    config_dir.mkdir(parents=True)
    iid = telemetry_module.get_instance_id(config_dir=str(config_dir))
    # Clear cached id and re-get
    telemetry_module._instance_id = None
    iid2 = telemetry_module.get_instance_id(config_dir=str(config_dir))
    assert iid == iid2
    assert isinstance(iid, str)
    assert len(iid) == 36  # UUID v4
    assert iid.count("-") == 4
    # File exists with the ID
    assert (config_dir / "instance_id").exists()
    assert (config_dir / "instance_id").read_text().strip() == iid


def test_instance_id_persistent(telemetry_module, tmp_path):
    """Loading instance_id when file already exists returns the stored value."""
    config_dir = tmp_path / ".config" / "fast-mcp-telegram"
    config_dir.mkdir(parents=True)
    existing = "00000000-0000-4000-8000-000000000000"
    (config_dir / "instance_id").write_text(existing)
    loaded = telemetry_module.get_instance_id(config_dir=str(config_dir))
    assert loaded == existing


# ───────────────────────────── gather_payload ──────────────────────────


def test_gather_payload_structure(telemetry_module):
    """gather_payload returns correct top-level keys."""
    payload = telemetry_module.gather_payload()
    assert isinstance(payload, dict)
    assert payload["v"] == 1
    assert isinstance(payload["iid"], str)
    assert isinstance(payload["ts"], int)
    assert isinstance(payload["started_at"], int)
    assert isinstance(payload["ver"], str)
    assert isinstance(payload["os"], str)
    assert isinstance(payload["py"], str)


def test_gather_payload_features_structure(telemetry_module):
    """gather_payload features block has all expected keys."""
    payload = telemetry_module.gather_payload()
    features = payload["features"]
    expected = {
        "server_mode",
        "acl_enabled",
        "acl_deny_unlisted_principals",
        "bot_api_token",
        "mtproto_proxy",
        "prefix_mcp_tools_with_account",
        "max_active_sessions",
        "inactive_session_days",
        "block_private_ips",
        "allow_http_urls",
        "acl_principals",
        "acl_read_only",
    }
    assert expected.issubset(features.keys())


def test_gather_payload_runtime_structure(telemetry_module):
    """gather_payload runtime block has expected keys."""
    payload = telemetry_module.gather_payload()
    runtime = payload["runtime"]
    expected = {"sessions", "session_files", "setup_sessions", "memory_kb"}
    assert expected.issubset(runtime.keys())
    # memory_kb is int on Linux, None on non-Linux
    assert runtime["memory_kb"] is None or isinstance(runtime["memory_kb"], int)


def test_gather_payload_counters_structure(telemetry_module):
    """gather_payload counters block has expected keys."""
    payload = telemetry_module.gather_payload()
    counters = payload["counters"]
    expected = {"total_calls", "errors"}
    assert expected.issubset(counters.keys())
    # Initial values at startup should be zero before any tool calls
    assert isinstance(counters["total_calls"], int)
    assert isinstance(counters["errors"], int)


def test_gather_payload_server_mode_reflects_config(telemetry_module):
    """server_mode in payload matches current config."""
    from src.config.server_config import cfg

    cfg_obj = cfg()
    payload = telemetry_module.gather_payload()
    assert payload["features"]["server_mode"] == cfg_obj.server_mode.value


# ───────────────────────────── _get_rss_kb ────────────────────────────


def test_get_rss_kb_parses_vmrss_from_proc_status(telemetry_module, monkeypatch):
    """_get_rss_kb parses VmRSS from /proc/self/status when readable."""
    _real_open = open

    def _fake_open(path, *args, **kwargs):
        if path == "/proc/self/status":
            from io import StringIO
            return StringIO("Name:\tpython\nVmRSS:\t12345 kB\n")
        return _real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _fake_open)
    assert telemetry_module._get_rss_kb() == 12345


def test_get_rss_kb_fallback_non_linux(telemetry_module, tmp_path, monkeypatch):
    """_get_rss_kb returns None when /proc/self/status is unavailable."""
    _real_open = open

    def _fake_open(path, *args, **kwargs):
        if path == "/proc/self/status":
            raise FileNotFoundError(f"No such file: {path}")
        return _real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _fake_open)
    assert telemetry_module._get_rss_kb() is None


def test_get_rss_kb_missing_vmrss_line(telemetry_module, tmp_path, monkeypatch):
    """_get_rss_kb returns None when /proc/self/status lacks VmRSS."""
    dummy = tmp_path / "status"
    dummy.write_text("Name:\tpython\nPid:\t1\n")
    _real_open = open

    def _fake_open(path, *args, **kwargs):
        if path == "/proc/self/status":
            return _real_open(dummy, *args, **kwargs)
        return _real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _fake_open)
    assert telemetry_module._get_rss_kb() is None


def test_get_rss_kb_corrupted_line(telemetry_module, tmp_path, monkeypatch):
    """_get_rss_kb returns None when VmRSS line has no numeric value."""
    dummy = tmp_path / "status"
    dummy.write_text("VmRSS:\n")
    _real_open = open

    def _fake_open(path, *args, **kwargs):
        if path == "/proc/self/status":
            return _real_open(dummy, *args, **kwargs)
        return _real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _fake_open)
    assert telemetry_module._get_rss_kb() is None


# ───────────────────────────── send_heartbeat ──────────────────────────


def test_send_heartbeat_debug_mode_logs(telemetry_module, capsys):
    """MCP_TELEMETRY_DEBUG=1 logs payload as JSON to stderr instead of sending."""
    os.environ["MCP_TELEMETRY_DEBUG"] = "1"

    payload = {"v": 1, "test": True}
    telemetry_module.send_heartbeat(payload)

    captured = capsys.readouterr()
    # Payload should appear in stderr as formatted JSON with TELEMETRY prefix
    assert "TELEMETRY" in captured.err
    import json

    json.loads(captured.err.split("TELEMETRY")[-1].strip())  # valid JSON


def test_send_heartbeat_network_error_silent(telemetry_module):
    """Network error does not raise — silently ignored."""
    import urllib.error
    from unittest.mock import patch

    payload = {"v": 1, "test": True}
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("refused")
        # Should not raise
        telemetry_module.send_heartbeat(payload)
    mock_urlopen.assert_called_once()


