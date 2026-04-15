# L0 实现任务拆分（Owner + 截止时间）

## 任务原则
- 截止时间按 Asia/Shanghai 时区
- `P0` 为阻塞主链路任务，必须优先完成
- `P1` 为非阻塞优化，可并行

## P0（阻塞主链路）

| ID | 任务 | Owner | 截止时间 | 依赖 | 交付标准 |
|---|---|---|---|---|---|
| L0-P0-01 | 本地传输实现（TCP 127.0.0.1）服务端骨架（ALSP_ADAPTER） | Rust-A | 2026-04-15 18:00 | 无 | 能接收/返回 v0 请求响应；支持并发连接 |
| L0-P0-02 | 本地传输客户端（Orchestrator 调用层） | Python-A | 2026-04-15 20:00 | L0-P0-01 | 可按 `request_id/trace_id` 发起调用并解析响应 |
| L0-P0-03 | `checks.run` 沙箱执行器字段落地 | Python-B | 2026-04-16 12:00 | L0-P0-02 | 支持 `cwd/command/args/timeout_ms/env_allowlist/max_output_kb` |
| L0-P0-04 | `checks.run` 安全策略（环境隔离/超时强杀/输出截断） | Python-B | 2026-04-16 18:00 | L0-P0-03 | 单测覆盖 3 条规则，异常路径返回标准错误码 |
| L0-P0-05 | Patchlet 错误返回实现（APPLY_FAILED/CONFLICT） | Rust-B | 2026-04-16 18:00 | 无 | 返回 `retryable` 和 `details(file,line,search_excerpt)` |
| L0-P0-06 | Orchestrator 错误路由绑定（重试/终止） | Python-A | 2026-04-17 12:00 | L0-P0-05 | `PATCHLET_APPLY_FAILED` 进入重试；`PATCHLET_CONFLICT` 进入 Repair 终止策略 |
| L0-P0-07 | 集成测试 1：正常链路 | QA-A | 2026-04-17 18:00 | L0-P0-01~06 | `Analyze -> Plan -> Execute -> Verify -> Done` 全链路通过 |
| L0-P0-08 | 集成测试 2：LSP 降级 | QA-A | 2026-04-18 12:00 | L0-P0-01~06 | 模拟 `ALSP_LSP_TIMEOUT` 并验证静态索引回退生效 |
| L0-P0-09 | 集成测试 3：补丁冲突 | QA-A | 2026-04-18 18:00 | L0-P0-05~06 | 模拟 `PATCHLET_SEARCH_MISS/CONFLICT`，验证 Repair 与错误码 |
| L0-P0-10 | CI 接入三条集成测试 | DevOps-A | 2026-04-19 12:00 | L0-P0-07~09 | PR 中自动执行并输出 trace_id |

## P1（非阻塞优化）

| ID | 任务 | Owner | 截止时间 | 依赖 | 交付标准 |
|---|---|---|---|---|---|
| L0-P1-01 | Named Pipe 传输 PoC（Windows） | Rust-A | 2026-04-20 18:00 | L0-P0-01 | PoC 可连通并给出性能对比 |
| L0-P1-02 | Unix Socket 传输 PoC（Linux/macOS） | Rust-A | 2026-04-21 18:00 | L0-P0-01 | PoC 可连通并给出性能对比 |
| L0-P1-03 | 协议示例文档扩展（更多错误样例） | Python-A | 2026-04-20 12:00 | L0-P0-05 | 新增至少 5 条真实请求/响应样例 |
| L0-P1-04 | trace 检索命令增强（CLI） | Python-C | 2026-04-21 12:00 | L0-P0-10 | 支持按 trace_id 查询节点耗时与错误码 |

## 负责人映射（临时）
- Rust-A：ALSP_ADAPTER 传输层
- Rust-B：Patchlet 错误语义
- Python-A：Orchestrator 协议调用与路由
- Python-B：Build-Check / checks.run 执行器
- Python-C：CLI 工具层
- QA-A：集成测试
- DevOps-A：CI

## 管理动作
- 每天 18:30 更新本文件状态（进行中/阻塞/完成）
- P0 任一任务延期超过 1 天，必须触发范围重排评审

## 执行更新（2026-04-14）
- [x] `L0-P0-01` 已完成
  - 交付：`engine/rust/alsp_adapter` TCP 服务骨架（`127.0.0.1:8787` 默认）
  - 能力：并发连接、v0 请求解析、标准响应回包、坏请求错误返回
  - 验证：`cargo check --manifest-path engine/rust/alsp_adapter/Cargo.toml` 通过
- [x] `L0-P0-02` 已完成
  - 交付：`orchestrator/langgraph_orchestrator/protocol_client.py` TCP 客户端调用层
  - 能力：`request_id/trace_id` 透传、`timeout_ms` 控制、响应校验、异常封装
  - 验证：`pytest -q tests/integration`（含客户端集成用例）通过
- [x] `L0-P0-03` 已完成
  - 交付：`checks.run` 执行器字段落地（`cwd/command/args/timeout_ms/env_allowlist/max_output_kb`）
  - 能力：执行命令并返回 `exit_code/stdout_tail/stderr_tail/timed_out`
  - 验证：`pytest -q tests/integration` 通过
- [x] `L0-P0-04` 已完成
  - 交付：`checks.run` 安全策略落地（env allowlist、超时强杀、输出截断）
  - 能力：仅注入 `env_allowlist`、超时后终止进程树、返回 `output_truncated`
  - 验证：`pytest -q tests/integration`（含安全策略测试）通过
- [x] `L0-P0-05` 已完成
  - 交付：Patchlet 错误返回实现（`PATCHLET_APPLY_FAILED` / `PATCHLET_CONFLICT`）
  - 能力：两类错误均返回 `retryable` 和 `details(file,line,search_excerpt)`
  - 验证：`cargo test --manifest-path engine/rust/patchlet/Cargo.toml` 通过
- [x] `L0-P0-06` 已完成
  - 交付：Orchestrator 错误路由绑定（Patchlet 错误码 -> 重试/终止策略）
  - 能力：`PATCHLET_APPLY_FAILED` 有界重试，`PATCHLET_CONFLICT/SEARCH_MISS` 进入 Repair 终止策略
  - 验证：`pytest -q tests/integration`（含路由测试）通过
- [x] `L0-P0-07` 已完成
  - 交付：正常链路集成测试（Analyze -> Plan -> Execute -> Verify -> Done）
  - 能力：最小编排执行器可产出完整状态序列并返回成功结果
  - 验证：`pytest -q tests/integration`（含 normal chain 测试）通过
- [x] `L0-P0-08` 已完成
  - 交付：LSP 降级集成测试（`ALSP_LSP_TIMEOUT` -> 静态索引回退）
  - 能力：降级后主流程不中断并可到达 `Done`
  - 验证：`pytest -q tests/integration`（含 fallback 测试）通过
- [x] `L0-P0-09` 已完成
  - 交付：补丁冲突集成测试（`PATCHLET_SEARCH_MISS/PATCHLET_CONFLICT` -> `Repair`）
  - 能力：冲突场景进入 Repair，输出正确错误码
  - 验证：`pytest -q tests/integration`（含 conflict/search miss 测试）通过
- [x] `L0-P0-10` 已完成
  - 交付：CI 接入并在 push/PR 自动执行集成测试
  - 能力：运行 `tests/integration` 并上传测试日志产物（可追踪 trace 输出）
  - 验证：CI 工作流配置已更新（`.github/workflows/ci.yml`）
- [x] `L0-P1-01` 已完成
  - 交付：Windows Named Pipe PoC 服务端（独立二进制）
  - 能力：支持行分隔 JSON 请求/响应，返回 `transport=named_pipe`
  - 验证：`cargo check --manifest-path engine/rust/alsp_adapter/Cargo.toml --bin named_pipe_poc` 通过
- [x] `L0-P1-02` 已完成
  - 交付：Unix Socket PoC 服务端（独立二进制，Unix 平台）
  - 能力：支持行分隔 JSON 请求/响应，返回 `transport=unix_socket`
  - 验证：`cargo check --manifest-path engine/rust/alsp_adapter/Cargo.toml --bin unix_socket_poc` 通过
- [x] `L0-P1-03` 已完成
  - 交付：协议示例文档扩展（5 组真实请求/响应）
  - 能力：覆盖成功、LSP 超时降级、Patchlet 可重试失败、Patchlet 冲突、checks.run
  - 验证：文档文件已落地（`docs/local_protocol_v0_examples.md`）
- [x] `L0-P1-04` 已完成
  - 交付：CLI trace 检索增强（按 `trace_id` 查询节点耗时与错误码）
  - 能力：从 JSONL 事件文件汇总 `nodes/total_duration_ms/error_codes`
  - 验证：`pytest -q tests/integration`（含 trace query 测试）通过
