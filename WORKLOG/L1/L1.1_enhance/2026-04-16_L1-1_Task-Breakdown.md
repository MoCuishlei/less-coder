# L1.1 Task Breakdown (2026-04-16)

日期：2026-04-16  
阶段：L1.1 Enhance（MVP 可用性加固）  
目标：围绕“随机目录启动 + 预热门禁 + 增量预热”场景，把 MVP 做到可稳定试用。

## 场景驱动验收主线（今日）

1. 用户在随机目录启动 MCP/`lesscoder server`（非仓库目录）。
2. 用户询问“能做什么”，AI 能识别并提示哪些方法依赖 warmup。
3. 用户直接调用预热依赖方法时，系统明确返回“需先 warmup”。
4. 用户执行 warmup 后，语义/图查询方法可正常使用。
5. 用户修改少量代码后，系统执行增量预热（非全量重建）。

## P0（本轮必须完成）

- [x] L1.1-P0-01：随机目录启动与项目根发现
  - 验收：支持 `--project-root` / `LESSCODER_HOME` / 自动发现。
  - 验收：失败时返回结构化 `tried_paths` 与 `next_action`。

- [x] L1.1-P0-02：能力清单与 warmup 依赖标注
  - 验收：`system.health` 返回方法分类与 `requires_warmup`。
  - 验收：区分“可直接调用”与“需 warmup 后调用”。

- [x] L1.1-P0-03：预热前门禁错误语义
  - 验收：预热依赖方法统一返回 `COMMON_PRECONDITION_REQUIRED`。
  - 验收：错误详情包含下一步动作 `system.warmup` 与示例 payload。

- [x] L1.1-P0-04：warmup 后语义/图方法可用
  - 验收：`system.warmup -> symbol.lookup` 链路可用。
  - 验收：`system.warmup -> graph.calls` 链路可用。
  - 验收：同会话内客户端不重复执行 warmup（客户端状态缓存）。

- [x] L1.1-P0-05：增量预热（非全量）
  - 验收：按 mtime/hash 识别变更文件并局部重建。
  - 验收：返回 `changed_files` / `reindexed_files` / `duration_ms`。

## P1（建议完成）

- [x] L1.1-P1-01：启动策略收敛（不提供隐式 `start`）
  - 约束：`system.warmup` 必须由用户/AI 显式传 `project_root/path` 参数。
  - 约束：不做“自动猜目录并一键 warmup -> server”。
- [x] L1.1-P1-02：端口占用检测与自动建议端口
- [x] L1.1-P1-03：发布前 dry-run（tag 前构建与元数据校验）

## 测试策略（与 P0 对齐）

- [x] 随机目录启动：`tests/integration/test_lesscoder_entrypoint.py`
- [x] 预热前门禁错误：`engine/rust/alsp_adapter/src/main.rs` 单测
- [x] warmup 后语义/图查询：`engine/rust/alsp_adapter/src/main.rs` 单测
- [x] 增量预热行为：Rust 单测 `warmup_incremental_reports_only_changed_java_files`
- [x] 回归：`pytest -q tests/integration` 全量绿（2026-04-16 已执行，37 passed）

## 执行更新（2026-04-16）

- [x] 完成 `L1.1-P0-03`：补齐预热前统一门禁错误，含 `next_action` 指引。
- [x] 完成 `L1.1-P0-04`：新增 `graph.calls` 最小可用路由，并纳入 warmup 门禁与健康清单。
- [x] 完成 `L1.1-P0-05`：`system.warmup` 增加 mtime 增量识别与统计字段返回。
- [x] 新增 Rust 单测 2 条：`graph_calls_requires_warmup_before_use`、`graph_calls_after_warmup_returns_ok_shape`。
- [x] 新增 Rust 单测 1 条：`warmup_incremental_reports_only_changed_java_files`。
- [x] 回归测试通过：
  - `cargo test --manifest-path engine/rust/alsp_adapter/Cargo.toml`
  - `pytest -q tests/integration/test_orchestrator_protocol_client.py tests/integration/test_real_chain_protocol.py tests/integration/test_lesscoder_entrypoint.py`
- [x] 完成 `L1.1-P1-01`：CLI `warmup/server` 要求显式 `--project-root|--manifest-path`，无参直接返回前置条件错误。
- [x] 完成 `L1.1-P1-02`：`server` 启动前执行端口占用检测，冲突时返回 `COMMON_PORT_IN_USE` 与 `suggested_port`。
- [x] 完成 `L1.1-P1-03`：新增 `lesscoder release-dry-run`，覆盖版本一致性、tag 校验、tests/build/pack/release-build。
