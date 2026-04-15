# L1 实现任务拆分（Owner + 截止时间）

## 目标
- 将 L0 的“骨架+模拟链路”升级为“真实 Java 联调链路”。
- 打通 `ALSP -> ALSP_ADAPTER -> Orchestrator -> Patchlet -> checks.run` 端到端。

## 优先级说明
- `P0`：阻塞主链路，必须优先完成
- `P1`：增强项，可并行

## P0（阻塞主链路）

| ID | 任务 | Owner | 截止时间 | 依赖 | 交付标准 |
|---|---|---|---|---|---|
| L1-P0-01 | 准备 Java 真实 fixture 项目（可复现 bug + 可跑测试） | Java-A | 2026-04-15 14:00 | 无 | `fixtures/java-sample` 可执行 `mvn test`，含 1 个可修复缺陷 |
| L1-P0-02 | ALSP Java 骨架提取最小实现（repo.map） | Rust-A | 2026-04-15 20:00 | L1-P0-01 | 返回类/方法签名与位置；可被 `repo.map` 调用 |
| L1-P0-03 | ALSP Java 符号查询最小实现（symbol.lookup） | Rust-A | 2026-04-16 12:00 | L1-P0-01 | 可按符号名返回定义位置（先静态索引） |
| L1-P0-04 | ALSP_ADAPTER 路由接入真实 ALSP（替换 echo） | Rust-B | 2026-04-16 18:00 | L1-P0-02~03 | `repo.map/symbol.lookup` 返回真实数据 |
| L1-P0-05 | Patchlet 对接真实文件修改（搜索替换 + 备份） | Rust-C | 2026-04-17 12:00 | L1-P0-01 | 可实际改 fixture 文件并生成可回滚备份 |
| L1-P0-06 | Orchestrator pipeline 替换真实调用（去 stub） | Python-A | 2026-04-17 18:00 | L1-P0-04~05 | 正常链路使用真实协议调用与真实 patch |
| L1-P0-07 | checks.run 对接真实 Java 验证命令（mvn test） | Python-B | 2026-04-18 12:00 | L1-P0-01 | 运行结果进入 pipeline Verify 阶段 |
| L1-P0-08 | 端到端集成测试（真实链路） | QA-A | 2026-04-18 18:00 | L1-P0-01~07 | 1 条真实修复任务可跑通到 `Done` |
| L1-P0-09 | 降级链路真实测试（LSP timeout -> 静态索引） | QA-A | 2026-04-19 12:00 | L1-P0-04~07 | 任务不中断，`fallback_used=true` |
| L1-P0-10 | 冲突链路真实测试（Patch conflict -> Repair） | QA-A | 2026-04-19 18:00 | L1-P0-05~07 | 输出正确错误码并进入 Repair |
| L1-P0-11 | CI 接入真实链路测试（分层执行） | DevOps-A | 2026-04-20 12:00 | L1-P0-08~10 | PR 自动执行真实 E2E（可拆夜间任务） |

## P1（增强项）

| ID | 任务 | Owner | 截止时间 | 依赖 | 交付标准 |
|---|---|---|---|---|---|
| L1-P1-01 | ALSP 索引增量更新（基于文件变更） | Rust-A | 2026-04-21 18:00 | L1-P0-02~03 | 单文件修改后仅局部重建 |
| L1-P1-02 | CLI `task run` 命令打通真实链路 | Python-C | 2026-04-21 18:00 | L1-P0-06~07 | 一条命令触发完整任务流程 |
| L1-P1-03 | 运行日志结构化增强（节点耗时/错误码） | Python-A | 2026-04-22 12:00 | L1-P0-06 | trace 输出可直接用于复盘 |
| L1-P1-04 | Java 任务基准集（3 个典型修复） | QA-A | 2026-04-22 18:00 | L1-P0-08 | 建立最小回归基准 |

## Owner 映射（沿用）
- Rust-A：ALSP（Java 解析/索引）
- Rust-B：ALSP_ADAPTER（协议路由）
- Rust-C：Patchlet
- Python-A：Orchestrator 编排
- Python-B：checks.run / 验证链路
- Python-C：CLI
- QA-A：集成与回归测试
- DevOps-A：CI/流水线
- Java-A：fixture 与测试样例维护

## 管理动作
- 每天 18:30 更新状态（进行中/阻塞/完成）
- P0 任一任务延期超过 1 天，触发范围重排评审

## 执行更新（2026-04-15）
- [x] `L1-P0-01` 已完成
  - 交付：`fixtures/java-sample` Maven Java 样例工程（含可复现缺陷）
  - 能力：`mvn test` 可执行；当前 3 个测试中 1 个失败，作为后续修复基线
  - 缺陷用例：`NameServiceTest.shouldReturnUnknownForBlank`
  - 验证：`mvn test` 已执行并稳定复现失败
- [x] `L1-P0-02` 已完成
  - 交付：`ALSP` Java `repo.map` 最小实现（静态骨架提取）
  - 能力：扫描 `.java` 文件并输出类/方法签名与行号（JSON）
  - 验证：`cargo test --manifest-path engine/rust/alsp/Cargo.toml` 与 `cargo run --manifest-path engine/rust/alsp/Cargo.toml -- fixtures/java-sample` 通过
- [x] `L1-P0-03` 已完成
  - 交付：`ALSP` Java `symbol.lookup` 最小实现（静态索引）
  - 能力：按符号名返回定义位置（文件、行号、签名、kind）
  - 验证：`cargo test --manifest-path engine/rust/alsp/Cargo.toml` 与 `cargo run --manifest-path engine/rust/alsp/Cargo.toml -- lookup fixtures/java-sample normalizeName` 通过
- [x] `L1-P0-04` 已完成
  - 交付：`ALSP_ADAPTER` 路由接入真实 `ALSP`（替换 echo）
  - 能力：`repo.map/symbol.lookup/symbol.lookup.static` 返回真实扫描结果；未知 action 返回 `ADAPTER_ROUTE_FAILED`
  - 验证：`cargo check --manifest-path engine/rust/alsp_adapter/Cargo.toml` 通过
- [x] `L1-P0-05` 已完成
  - 交付：Patchlet 真实文件修改能力（搜索替换 + 备份 + 回滚）
  - 能力：命中后写入 `.patchlet.bak` 备份，支持从备份回滚
  - 验证：`cargo test --manifest-path engine/rust/patchlet/Cargo.toml` 通过（4 tests）
- [x] `L1-P0-06` 已完成
  - 交付：Orchestrator pipeline 真实调用链（协议调用 + 真实 patch.apply）
  - 能力：通过 `LocalProtocolClient` 调 `repo.map/symbol.lookup/patch.apply`，Verify 走 `checks.run`
  - 验证：`cargo check --manifest-path engine/rust/alsp_adapter/Cargo.toml` 与 `pytest -q tests/integration`（17 passed）通过
- [x] `L1-P0-07` 已完成
  - 交付：`checks.run` 与真实 Java `mvn test` 验证链路打通
  - 能力：Verify 阶段支持最小必要系统变量白名单（PATH/SystemRoot/ComSpec/TEMP 等），保持白名单策略
  - 验证：`pytest -q tests/integration/test_checks_runner_java_maven.py` 与 `pytest -q tests/integration`（18 passed）通过
- [x] `L1-P0-08` 已完成
  - 交付：真实端到端集成测试（启动真实 `alsp_adapter`，跑 `run_real_chain` 到 `Done`）
  - 能力：可自动修复 Java fixture 缺陷并通过 Verify（`mvn test`）
  - 验证：`pytest -q tests/integration/test_real_e2e_done.py` 与 `pytest -q tests/integration`（19 passed）通过
  - 注意：涉及 fixture 文件改写的测试需串行执行，避免并发竞争
- [x] `L1-P0-09` 已完成
  - 交付：真实 LSP 降级链路（`ALSP_LSP_TIMEOUT` -> `symbol.lookup.static`）
  - 能力：强制超时场景下自动降级且主流程可达 `Done`，`fallback_used=true`
  - 验证：`pytest -q tests/integration`（20 passed）通过
  - 修正：真实 Java 相关测试改为临时目录副本运行，避免 fixture 状态污染
- [x] `L1-P0-10` 已完成
  - 交付：真实补丁冲突链路测试（`PATCHLET_SEARCH_MISS` / `PATCHLET_CONFLICT`）
  - 能力：两类错误码均进入 `Repair` 并返回正确 `error_code`
  - 验证：`pytest -q tests/integration/test_real_e2e_patch_conflict.py` 与 `pytest -q tests/integration`（22 passed）通过
- [x] `L1-P0-11` 已完成
  - 交付：CI 接入真实链路测试并分层执行（fast + real_e2e）
  - 能力：CI 自动安装 Java/Rust，先跑快测，再跑真实 E2E；上传分层日志
  - 验证：本地分层命令通过（`pytest -q tests/integration -k "not real_e2e"` 与 `pytest -q tests/integration -k "real_e2e"`）

- [x] `L1-P1-01` 已完成
  - 交付：ALSP 增量索引能力（基于文件 mtime+size 复用未变化文件）
  - 能力：`build_java_repo_map_incremental` 只重建变化文件，返回增量统计
  - 验证：`cargo test --manifest-path engine/rust/alsp/Cargo.toml`（6 tests）通过
- [x] `L1-P1-02` 已完成
  - 交付：CLI `task run` 命令打通真实链路
  - 能力：支持 `project-root/adapter-host/adapter-port/trace-id/verify` 参数并输出结构化结果
  - 验证：`pytest -q tests/integration/test_cli_task_run.py` 与 `pytest -q tests/integration`（23 passed）通过
- [x] `L1-P1-03` 已完成
  - 交付：结构化运行日志增强（JSONL trace events）
  - 能力：记录 `trace_id/node/duration_ms/status/error_code`，支持自定义 events 文件路径
  - 验证：`pytest -q tests/integration`（24 passed）通过
- [x] `L1-P1-04` 已完成
  - 交付：Java 任务基准集（3 个典型修复）与统一 manifest
  - 能力：覆盖输入校验、边界条件、聚合计算 3 类典型修复；可直接用于最小回归
  - 验证：`pytest -q tests/integration/test_java_benchmark_set.py` 与 `pytest -q tests/integration`（25 passed）通过
