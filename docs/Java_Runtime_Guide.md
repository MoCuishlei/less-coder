# Code-Native Engine Java 运行手册

更新时间：2026-04-15  
适用阶段：L1（Java）

## 1. 目标与范围

当前版本目标是跑通一个可用的本地闭环：

`Analyze -> Plan -> Execute -> Verify -> Done`

当前范围聚焦 Java 项目，支持在本地通过协议调用 ALSP 与 Patchlet，由 Orchestrator（LangGraph）编排完成“定位-修改-验证”。

## 2. 能力清单

- `ALSP`（Rust）
  - `repo.map`：项目骨架抽取（类/方法签名级）
  - `symbol.lookup`：符号定位（静态索引）
  - LSP 超时降级：可回退静态索引
- `ALSP_ADAPTER`（Rust）
  - 本地协议 v0 服务端
  - 当前主通道：TCP（127.0.0.1）
- `Patchlet`（Rust）
  - SEARCH/REPLACE 原子补丁应用
  - 备份与回滚
  - 冲突与失败错误码
- `Orchestrator`（Python + LangGraph）
  - 状态机编排（含 Repair 分支）
  - Build-Check 验证闭环
  - 错误路由（可重试/不可重试）
- `CLI`（Python）
  - `task run`
  - trace 查询
- `CI`
  - 集成测试自动执行
  - 分层执行（fast / real_e2e）

## 3. 非目标（当前阶段暂不覆盖）

- 非 Java 语言的完整生产支持（Go/JS/TS/C/C++ 在 L2 推进）
- Desktop/IDE 完整产品化 UI（目前 CLI 为主）
- 外部 MCP 生态对接的完整产品化交付（当前以内部本地协议为主）

## 4. 架构与模块

```text
engine/rust/alsp            # 语义与索引能力（Tree-sitter/LSP/Symbolic）
engine/rust/alsp_adapter    # 本地协议服务层（TCP）
engine/rust/patchlet        # 原子 Diff 应用与回滚
orchestrator/langgraph_orchestrator  # 状态机与闭环执行
clients/cli                 # CLI 入口
tests/integration           # 集成与真实链路测试
```

## 5. 协议与错误语义（v0）

- 请求/响应统一带 `trace_id`
- `checks.run` 安全字段：
  - `cwd`
  - `command`
  - `args[]`
  - `timeout_ms`
  - `env_allowlist{}`
  - `max_output_kb`
- `checks.run` 返回补充：
  - `exit_code`
  - `stdout_tail`
  - `stderr_tail`
  - `timed_out`
- Patchlet 错误语义：
  - `PATCHLET_APPLY_FAILED`：可重试失败（`retryable=true`）
  - `PATCHLET_CONFLICT`：逻辑冲突（`retryable=false`）
  - 两者均要求 `details`（文件、行号、search 摘要）

## 6. 运行前准备

建议环境（Windows）：

- Rust toolchain（stable）
- Python 3.11+（当前环境已使用 3.13 运行测试）
- Java 17+
- Maven 3.9+

安装方式（发布后）：

```powershell
pip install lesscoder
npm i -g @lesscoder/cli
```

发布前（源码安装）：

```powershell
pip install -e .
```

## 7. 快速验证命令

在仓库根目录执行：

```powershell
pytest -q tests/integration
```

按模块验证：

```powershell
cargo test --manifest-path engine/rust/alsp/Cargo.toml
cargo test --manifest-path engine/rust/alsp_adapter/Cargo.toml
cargo test --manifest-path engine/rust/patchlet/Cargo.toml
```

CLI 与服务入口（推荐）：

```powershell
python -m clients.cli.lesscoder --help
python -m clients.cli.lesscoder server --host 127.0.0.1 --port 8787
python -m clients.cli.lesscoder run --project-root fixtures/java-sample
python -m clients.cli.lesscoder trace --trace-id <trace_id>
```

## 8. 验收标准（当前版本）

- [x] Java 项目可跑通 Done 链路
- [x] LSP 超时可降级并不中断主流程
- [x] Patch 冲突可进入 Repair 并给出正确错误码
- [x] Build-Check 形成自动验证闭环
- [x] CLI 可触发任务执行与 trace 查询
- [x] CI 已接入并可稳定执行集成测试

## 9. 已知边界与风险

- 目前“热门语言全量支持”尚未纳入 MVP 交付范围（属于 L2）
- 协议已冻结 v0，新增字段需走评审
- 真实工程复杂度上升后，需继续补充基准集和回归用例

## 10. 下一阶段（L2/L3）建议

1. 扩展语言：Go / JS / TS / C / C++（保留模块物理隔离）
2. 完善混合检索：SQLite + Vector 查询策略与性能基线
3. 做稳定性压测与故障注入（超时、锁冲突、并发写）
4. 对接 Adapter 预留接口（Desktop/IDE）

## 11. 关联文档

- `C:/Users/14724/.gemini/antigravity/less-coder/PROJECT_GUIDE.md`
- `C:/Users/14724/.gemini/antigravity/less-coder/docs/local_protocol_v0.md`
- `C:/Users/14724/.gemini/antigravity/less-coder/docs/local_protocol_v0_examples.md`
- `C:/Users/14724/.gemini/antigravity/less-coder/docs/v0_Preview.md`
- `C:/Users/14724/.gemini/antigravity/less-coder/WORKLOG/README.md`
- `C:/Users/14724/.gemini/antigravity/less-coder/WORKLOG/L1/2026-04-15_L1_Task-Breakdown.md`
