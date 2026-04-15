# 本地协议 v0 示例（Examples）

本文档给出可直接联调的请求/响应样例，覆盖主链路和关键错误场景。

---

## 1) `repo.map` 成功示例

请求：

```json
{
  "version": "v0",
  "request_id": "req_1001",
  "trace_id": "tr_20260414_001",
  "session_id": "sess_a",
  "source": "orchestrator",
  "target": "alsp_adapter",
  "action": "repo.map",
  "payload": {
    "path": "/workspace/demo",
    "language": "java"
  },
  "meta": {
    "timeout_ms": 30000
  }
}
```

响应：

```json
{
  "version": "v0",
  "request_id": "req_1001",
  "trace_id": "tr_20260414_001",
  "status": "ok",
  "data": {
    "files": 128,
    "symbols": 642
  },
  "error": null,
  "fallback_used": false,
  "cost": {
    "duration_ms": 36
  }
}
```

---

## 2) `symbol.lookup` LSP 超时并降级示例

请求：

```json
{
  "version": "v0",
  "request_id": "req_1002",
  "trace_id": "tr_20260414_001",
  "session_id": "sess_a",
  "source": "orchestrator",
  "target": "alsp_adapter",
  "action": "symbol.lookup",
  "payload": {
    "symbol": "AService#process",
    "prefer": "lsp"
  },
  "meta": {
    "timeout_ms": 2000
  }
}
```

响应：

```json
{
  "version": "v0",
  "request_id": "req_1002",
  "trace_id": "tr_20260414_001",
  "status": "ok",
  "data": {
    "symbol": "AService#process",
    "location": "src/main/java/com/acme/AService.java:87",
    "provider": "static_index"
  },
  "error": null,
  "fallback_used": true,
  "cost": {
    "duration_ms": 74
  }
}
```

---

## 3) `patch.apply` 可重试失败（`PATCHLET_APPLY_FAILED`）

请求：

```json
{
  "version": "v0",
  "request_id": "req_1003",
  "trace_id": "tr_20260414_001",
  "session_id": "sess_a",
  "source": "orchestrator",
  "target": "patchlet",
  "action": "patch.apply",
  "payload": {
    "target": "src/main/java/com/acme/A.java",
    "search_replace_blocks": [
      {
        "search": "if (x == null) {",
        "replace": "if (x == null || x.isBlank()) {"
      }
    ]
  },
  "meta": {
    "timeout_ms": 10000
  }
}
```

响应：

```json
{
  "version": "v0",
  "request_id": "req_1003",
  "trace_id": "tr_20260414_001",
  "status": "error",
  "data": null,
  "error": {
    "code": "PATCHLET_APPLY_FAILED",
    "message": "patch apply failed due to transient io error",
    "retryable": true,
    "node": "Execute",
    "details": {
      "file": "src/main/java/com/acme/A.java",
      "line": 128,
      "search_excerpt": "if (x == null) {"
    }
  },
  "fallback_used": false,
  "cost": {
    "duration_ms": 7
  }
}
```

---

## 4) `patch.apply` 冲突失败（`PATCHLET_CONFLICT`）

请求：

```json
{
  "version": "v0",
  "request_id": "req_1004",
  "trace_id": "tr_20260414_001",
  "session_id": "sess_a",
  "source": "orchestrator",
  "target": "patchlet",
  "action": "patch.apply",
  "payload": {
    "target": "src/main/java/com/acme/A.java",
    "search_replace_blocks": [
      {
        "search": "public void process() {",
        "replace": "public void process(Request req) {"
      }
    ]
  },
  "meta": {
    "timeout_ms": 10000
  }
}
```

响应：

```json
{
  "version": "v0",
  "request_id": "req_1004",
  "trace_id": "tr_20260414_001",
  "status": "error",
  "data": null,
  "error": {
    "code": "PATCHLET_CONFLICT",
    "message": "search block conflict: multiple ambiguous matches",
    "retryable": false,
    "node": "Execute",
    "details": {
      "file": "src/main/java/com/acme/A.java",
      "line": 96,
      "search_excerpt": "public void process() {"
    }
  },
  "fallback_used": false,
  "cost": {
    "duration_ms": 3
  }
}
```

---

## 5) `checks.run` 成功示例

请求：

```json
{
  "version": "v0",
  "request_id": "req_1005",
  "trace_id": "tr_20260414_001",
  "session_id": "sess_a",
  "source": "orchestrator",
  "target": "orchestrator",
  "action": "checks.run",
  "payload": {
    "cwd": "/workspace/demo",
    "command": "mvn",
    "args": ["test"],
    "timeout_ms": 120000,
    "env_allowlist": {
      "JAVA_HOME": "/opt/jdk-21"
    },
    "max_output_kb": 512
  },
  "meta": {
    "timeout_ms": 130000
  }
}
```

响应：

```json
{
  "version": "v0",
  "request_id": "req_1005",
  "trace_id": "tr_20260414_001",
  "status": "ok",
  "data": {
    "exit_code": 0,
    "stdout_tail": "BUILD SUCCESS",
    "stderr_tail": "",
    "timed_out": false,
    "output_truncated": false
  },
  "error": null,
  "fallback_used": false,
  "cost": {
    "duration_ms": 4521
  }
}
```
