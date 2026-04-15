# 本地协议 v0 规范（ALSP_ADAPTER / Patchlet）

状态：`v0-frozen`  
生效日期：`2026-04-14`

## 1. 目标

定义项目内部本地协议 v0，统一：
- 请求结构
- 响应结构
- 错误码
- `trace_id`

适用范围：
- `Orchestrator -> ALSP_ADAPTER`
- `Orchestrator -> Patchlet`（或经 ALSP_ADAPTER 转发）

---

## 2. 传输与编码

- 传输：本地 JSON-RPC 风格
- 首选：`TCP 127.0.0.1`
- 回退策略：
  - Windows 可选 `Named Pipe`（优化项，非 v0 阻塞）
  - Linux/macOS 可选 `Unix Socket`（优化项，非 v0 阻塞）
- 编码：`UTF-8` + `application/json`
- 幂等：读请求必须幂等；写请求通过 `request_id` + 幂等键防重放（v0 可选）

---

## 3. 通用请求结构

```json
{
  "version": "v0",
  "request_id": "req_01J...",
  "trace_id": "tr_01J...",
  "session_id": "sess_01J...",
  "source": "orchestrator",
  "target": "alsp_adapter",
  "action": "symbol.lookup",
  "payload": {},
  "meta": {
    "timeout_ms": 30000,
    "locale": "zh-CN"
  }
}
```

字段约束：
- `version`：固定 `v0`
- `request_id`：单请求唯一
- `trace_id`：单任务全链路复用
- `session_id`：会话级可选
- `action`：`domain.verb` 形式
- `payload`：业务参数
- `meta.timeout_ms`：默认 30000，最大 120000

---

## 4. 通用响应结构

```json
{
  "version": "v0",
  "request_id": "req_01J...",
  "trace_id": "tr_01J...",
  "status": "ok",
  "data": {},
  "error": null,
  "fallback_used": false,
  "cost": {
    "duration_ms": 42
  }
}
```

字段约束：
- `status`：`ok | error`
- `data`：成功时必填
- `error`：失败时必填
- `fallback_used`：是否发生降级（如 LSP -> 静态索引）

---

## 5. 错误结构与错误码

## 5.1 错误对象

```json
{
  "code": "ALSP_LSP_TIMEOUT",
  "message": "lsp request timeout",
  "retryable": true,
  "node": "Analyze",
  "details": {}
}
```

## 5.2 错误码命名规则

- 规则：`<DOMAIN>_<CATEGORY>_<DETAIL>`
- 示例：`ALSP_LSP_TIMEOUT`
- 域：
  - `ALSP`
  - `ADAPTER`
  - `PATCHLET`
  - `ORCH`
  - `COMMON`

## 5.3 v0 错误码基线

| 错误码 | 含义 | retryable |
|---|---|---|
| `COMMON_BAD_REQUEST` | 参数不合法/缺字段 | false |
| `COMMON_UNAUTHORIZED` | 权限不足 | false |
| `COMMON_TIMEOUT` | 通用超时 | true |
| `COMMON_INTERNAL` | 未分类内部错误 | true |
| `ALSP_SYMBOL_NOT_FOUND` | 符号未命中 | false |
| `ALSP_LSP_UNAVAILABLE` | LSP 不可用 | true |
| `ALSP_LSP_TIMEOUT` | LSP 请求超时 | true |
| `ALSP_INDEX_STALE` | 索引过期需重建 | true |
| `ADAPTER_ROUTE_FAILED` | 路由策略失败 | true |
| `PATCHLET_SEARCH_MISS` | SEARCH 块未命中 | false |
| `PATCHLET_CONFLICT` | 补丁冲突 | false |
| `PATCHLET_APPLY_FAILED` | 应用失败（可重试） | true |
| `ORCH_NODE_FAILED` | 编排节点失败 | true |
| `ORCH_RETRY_EXHAUSTED` | 重试次数耗尽 | false |

---

## 6. trace_id 规范

- 生成时机：`CLI task run` 开始时生成
- 生命周期：一次任务全链路复用同一个 `trace_id`
- 透传要求：
  - CLI -> Orchestrator（生成/注入）
  - Orchestrator -> ALSP_ADAPTER / Patchlet（强制透传）
  - 响应必须原样返回 `trace_id`
- 日志格式：每行结构化日志必须包含 `trace_id`、`request_id`

---

## 7. action 清单（v0 最小集）

| action | 模块 | 说明 |
|---|---|---|
| `repo.scan` | ALSP_ADAPTER | 扫描项目（全量/增量） |
| `repo.map` | ALSP_ADAPTER | 获取骨架 map |
| `symbol.lookup` | ALSP_ADAPTER | 符号查询 |
| `symbol.references` | ALSP_ADAPTER | 引用查询 |
| `symbol.definition` | ALSP_ADAPTER | 定义跳转 |
| `patch.apply` | Patchlet | 应用 SEARCH/REPLACE |
| `checks.run` | Orchestrator/Runner | 执行构建测试 |
| `trace.get` | Orchestrator | 获取任务轨迹 |

---

## 8. `checks.run` 沙箱字段（v0 固化）

请求 `payload` 字段：

```json
{
  "cwd": "/abs/path/to/project",
  "command": "mvn",
  "args": ["test"],
  "timeout_ms": 120000,
  "env_allowlist": {
    "JAVA_HOME": "/path/jdk",
    "MAVEN_OPTS": "-Xmx1g"
  },
  "max_output_kb": 512
}
```

安全规则：
- 禁止继承全量环境变量，仅注入 `env_allowlist`
- 超时强杀进程树
- 标准输出/错误输出按 `max_output_kb` 截断

响应 `data` 至少包含：
- `exit_code`
- `stdout_tail`
- `stderr_tail`
- `timed_out`

---

## 9. Patchlet 错误样例（v0）

## 9.1 `PATCHLET_APPLY_FAILED`（可重试）

```json
{
  "version": "v0",
  "request_id": "req_01J...",
  "trace_id": "tr_01J...",
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
  "fallback_used": false
}
```

## 9.2 `PATCHLET_CONFLICT`（不可重试）

```json
{
  "version": "v0",
  "request_id": "req_01J...",
  "trace_id": "tr_01J...",
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
  "fallback_used": false
}
```

---

## 10. 集成测试基线用例（v0）

- 用例 1：正常链路  
  `Analyze -> Plan -> Execute -> Verify -> Done`
- 用例 2：LSP 降级  
  模拟 `ALSP_LSP_TIMEOUT`，确认回退静态索引且流程不中断
- 用例 3：补丁冲突  
  模拟 `PATCHLET_SEARCH_MISS`/`PATCHLET_CONFLICT`，确认进入 `Repair` 并输出正确错误码

---

## 11. 兼容与演进

- v0 原则：字段可新增、不可删除；语义不可破坏
- 版本升级：通过 `version` 字段判定；v1 开始引入 capability 协商
- 不兼容变更必须升级主版本（`v0 -> v1`）

---

## 12. 评审通过门槛（Gate）

- 所有核心模块对通用请求/响应结构无歧义
- 错误码覆盖 MVP 主链路失败场景
- `trace_id` 透传链路经集成测试验证通过
- action 清单可支撑 Java MVP 全流程
