# lesscoder MCP 方法清单（MVP）

更新时间：2026-04-16  
适用范围：Java 主线 MVP

## 1. 设计目标

对外提供稳定、可实现、可测试的 MCP 方法面，并明确“哪些方法需要在预热完成后使用”。

## 2. 方法分层

### 2.1 `system`（系统级）

- `system.health`
  - 作用：检查服务存活、版本、组件状态。
  - 预热要求：否。
- `system.warmup`
  - 作用：执行环境检查与索引预热（可包含构建缓存、语义缓存初始化）。
  - 预热要求：否（该方法本身就是预热入口）。

### 2.2 `context`（上下文与语义）

- `repo.map`
  - 作用：返回仓库骨架（类/方法签名级）。
  - 预热要求：建议是（未预热可自动降级并给 warning）。
- `symbol.lookup`
  - 作用：按符号名定位定义（优先 LSP）。
  - 预热要求：是。
- `symbol.lookup.static`
  - 作用：静态索引定位（LSP 降级路径）。
  - 预热要求：是。
- `symbol.resolve`（规划中）
  - 作用：通过 `symbol + class_name + file_hint` 精确消歧。
  - 预热要求：是。

### 2.3 `graph`（调用图与影响面，规划中）

- `graph.calls`
  - 作用：查询调用链（caller/callee）。
  - 预热要求：是。
- `symbol.references`
  - 作用：查询符号引用点（读/写/调用）。
  - 预热要求：是。
- `graph.impact`
  - 作用：分析改动影响范围（符号与测试）。
  - 预热要求：是。

### 2.4 `edit`（编辑）

- `patch.apply`
  - 作用：按 Search/Replace 原子应用补丁。
  - 预热要求：否（建议在 `context` 完成后调用）。
- `patch.rollback`（规划中）
  - 作用：基于备份文件回滚补丁。
  - 预热要求：否。

### 2.5 `verify`（验证）

- `checks.run`
  - 作用：执行构建/测试命令。
  - 预热要求：否。

### 2.6 `task/trace`（编排与观测）

- `task.run`（规划中，对外统一入口）
  - 作用：一键执行 Analyze -> Plan -> Execute -> Verify。
  - 预热要求：内部自动处理。
- `trace.query`（规划中，对外接口）
  - 作用：按 `trace_id` 查询节点耗时与错误码。
  - 预热要求：否。

## 3. 预热依赖矩阵

| 方法 | 是否必须先 warmup | 未预热行为 |
|---|---|---|
| `system.health` | 否 | 正常返回 |
| `system.warmup` | 否 | 执行预热 |
| `repo.map` | 建议 | 可降级，返回 warning |
| `symbol.lookup` | 是 | 返回 `COMMON_PRECONDITION_REQUIRED` 或内部触发 warmup |
| `symbol.lookup.static` | 是 | 返回 `COMMON_PRECONDITION_REQUIRED` 或内部触发 warmup |
| `symbol.resolve` | 是 | 同上 |
| `graph.calls` | 是 | 同上 |
| `symbol.references` | 是 | 同上 |
| `graph.impact` | 是 | 同上 |
| `patch.apply` | 否 | 正常执行 |
| `checks.run` | 否 | 正常执行 |

## 4. 推荐调用顺序

1. `system.health`
2. `system.warmup`
3. `repo.map`
4. `symbol.lookup` / `symbol.resolve`
5. `graph.calls`（需要时）
6. `patch.apply`
7. `checks.run`
8. `trace.query`（需要时）

## 5. 响应与错误码规范

所有方法统一响应结构：

- 成功：`status=ok`, `data`, `trace_id`, `cost`
- 失败：`status=error`, `error.code`, `error.message`, `error.retryable`, `error.details`, `trace_id`

建议错误码分组：

- `COMMON_*`：参数错误、前置条件、超时、内部异常
- `ALSP_*`：符号与语义解析
- `PATCHLET_*`：补丁冲突、应用失败
- `CHECKS_*`：命令执行、沙箱与超时
- `ORCH_*`：编排节点失败

新增建议：

- `COMMON_PRECONDITION_REQUIRED`：未完成 warmup 且方法需要预热

## 6. 对外版本策略

- 当前对外宣称：`v0`（稳定核心能力）。
- `graph.*` 与 `symbol.resolve` 先标记为 `experimental`，通过 capability 字段公开。
- 后续以 `v0.x` 增量扩展，不破坏既有字段语义。
