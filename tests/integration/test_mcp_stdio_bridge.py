import json

from clients.cli.mcp_stdio import BridgeConfig, handle_mcp_request


def test_initialize_returns_capabilities():
    req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    resp = handle_mcp_request(req, BridgeConfig())
    assert resp is not None
    assert resp["id"] == 1
    assert "result" in resp
    assert "capabilities" in resp["result"]


def test_tools_list_contains_system_health():
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    resp = handle_mcp_request(req, BridgeConfig())
    assert resp is not None
    tools = resp["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "system_health" in names
    assert "system_warmup" in names


def test_tools_call_unknown_returns_error():
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "nope", "arguments": {}},
    }
    resp = handle_mcp_request(req, BridgeConfig())
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32602


def test_notification_initialized_no_response():
    req = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    resp = handle_mcp_request(req, BridgeConfig())
    assert resp is None


def test_tools_call_wraps_adapter_response(monkeypatch):
    def fake_call(_cfg, action, payload):
        return {"status": "ok", "action": action, "payload": payload}

    from clients.cli import mcp_stdio

    monkeypatch.setattr(mcp_stdio, "_call_adapter", fake_call)
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "system_health", "arguments": {}},
    }
    resp = handle_mcp_request(req, BridgeConfig())
    assert resp is not None
    content = resp["result"]["content"][0]["text"]
    parsed = json.loads(content)
    assert parsed["status"] == "ok"
    assert parsed["action"] == "system.health"
