# Code-Native Engine 项目指导（v2）

## 1. 目标与范围

本项目目标是交付一个可用的端到端最小产品（MVP），支持 AI 在本地 Java 代码库完成：
1. 理解代码（语义定位）  
2. 生成最小补丁（原子 Diff）  
3. 自动验证（Build-Check）  
4. 失败重试与回滚（LangGraph 闭环）

MVP 语言：`Java`（仅首发验证）。  
首发前端：`CLI`。  
内部协议：本地协议（不强制 MCP）。  
对外能力：可通过 `ALSP_ADAPTER` 以 MCP 形式独立输出。

产品目标范围（非 MVP 限制）：后续扩展到热门语言全量支持（Go / Java / JavaScript / TypeScript / C / C++ 等）。

---

## 2. 模块划分（唯一口径）

## 2.1 模块总览

1. `ALSP`（Rust）  
语义核心服务层：Tree-sitter、LSP、Symbolic RAG、SQLite+Vector 混合检索。

2. `ALSP_ADAPTER`（Rust）  
功能出口层：统一对外 API，本地协议优先；可选暴露 MCP。

3. `Orchestrator`（Python + LangGraph）  
AI 编排层：Analyze / Plan / Execute / Verify / Repair / Done；含 Build-Check。

4. `Patchlet`（Rust）  
原子 Diff 引擎：SEARCH/REPLACE 解析、应用、冲突处理、回滚。

5. `CLI`（Rust 或 Python）  
首发交互层：任务发起、进度展示、结果与 trace 输出。

6. `Client Adapter`（预留）  
后续接入 Desktop/IDE/其他客户端，不侵入核心流程。

## 2.2 边界约束

- `Orchestrator` 只能调用 `ALSP_ADAPTER` / `Patchlet` 对外契约，不直连 `ALSP` 内部实现。
- `ALSP` 只负责语义与检索，不承载编排逻辑。
- `Patchlet` 只负责补丁与文件原子写，不承载任务规划。
- MCP 仅作为对外接口，不作为项目内部强依赖。

---

## 3. 通信与调用链

## 3.1 内部调用

- `CLI -> Orchestrator`
- `Orchestrator -> ALSP_ADAPTER`（本地协议）
- `Orchestrator -> Patchlet`（本地协议，或经 ALSP_ADAPTER 转发）

## 3.2 外部调用（可选）

- 第三方 AI/客户端 -> `ALSP_ADAPTER(MCP)`

---

## 4. 技术功能点（What）

## 4.1 ALSP（语义与检索）

- Java 项目扫描（全量 + 增量）
- Tree-sitter 骨架提取（类/方法/签名/注释/导入）
- 符号索引（定义/引用/位置）
- Symbolic RAG（符号优先，向量补充）
- LSP 能力（`definition/reference/hover/type`）
- 统一 IR 输出（含来源与置信度）

## 4.2 ALSP_ADAPTER（能力出口）

- 统一查询接口
- 路由策略（LSP 优先/静态优先/混合）
- 本地协议服务
- 可选 MCP 协议服务
- 会话治理（超时、限流、失败码）

## 4.3 Patchlet（补丁引擎）

- SEARCH/REPLACE 协议解析
- 最小变更写入
- 冲突检测与报告
- 原子写 + 回滚点

## 4.4 Orchestrator（AI 编排）

- LangGraph 状态机
- L1-L4 上下文加载与裁剪
- 任务规划与工具调度
- Build-Check 自动验证
- 失败分类重试（有上限）
- 国际化输出策略

## 4.5 CLI / Client Adapter

- CLI 命令：`task run / task trace / task replay / task config`
- 预留 Adapter：桌面端和 IDE 的消息映射、流式状态订阅

---

## 5. 核心实现原理（Why / How）

## 5.1 Tree-sitter

增量语法树只抽取“声明级骨架”，避免全文件上下文注入，降低 token 消耗。

## 5.2 Symbolic RAG

优先符号精确定位（定义/引用链），向量检索仅用于补充，减少语义噪声。

## 5.3 LSP + 静态索引协同

LSP 提供强语义（类型/跳转）；静态索引提供稳定回退。  
策略：LSP 失败自动降级静态索引，保证可用性。

## 5.4 原子 Diff

通过 SEARCH/REPLACE 做最小修改，不重写整文件；应用失败可定位冲突并回滚。

## 5.5 LangGraph 闭环

Analyze -> Plan -> Execute -> Verify -> Repair -> Done。  
Repair 必须有限次重试，避免无限循环。

---

## 6. MVP（Java + LangGraph + CLI）定义

## 6.1 MVP 必含能力

- Java: Tree-sitter + Symbolic RAG + LSP（jdtls）
- Rust: Patchlet 原子补丁
- Python: LangGraph 编排 + Build-Check
- CLI: 可发起并追踪任务
- Trace: 每次 run 有唯一 `trace_id`

## 6.2 MVP 端到端流程

1. 用户在 CLI 提交任务。  
2. `Analyze`：拉取 repo map 与符号信息。  
3. `Plan`：确定修改点与验证命令。  
4. `Execute`：生成并应用 SEARCH/REPLACE。  
5. `Verify`：执行 `mvn test`（或项目配置命令）。  
6. 失败进入 `Repair`（有限重试）。  
7. 成功进入 `Done` 输出变更和验证结果。

## 6.3 MVP 非目标

- 不支持多语言并发（仅 Java）
- 不做复杂图形 UI
- 不做策略学习系统

## 6.4 MVP 与产品最终范围关系（重要）

- MVP 只用于验证端到端闭环可用性，因此先收敛到 Java。
- 产品正式路线是多语言扩展，不是只做 Java。
- 多语言扩展阶段将复用同一套 `ALSP` 能力模型与 `ALSP_ADAPTER` 对外契约。

---

## 6.5 多语言扩展路线（Post-MVP）

### Phase A（优先）
- JavaScript / TypeScript
- Go

### Phase B
- C / C++
- Python（按业务优先级可前置）

### 每个语言的接入完成标准
- Tree-sitter 骨架提取可用
- LSP definition/reference 可用
- Symbolic RAG 可用（符号优先 + 向量补充）
- 回归 fixture 与基准测试通过

---

## 7. 全量 Checklist（执行清单）

## 7.1 架构与工程基线

- [ ] 冻结模块命名与边界（ALSP/ALSP_ADAPTER/Orchestrator/Patchlet/CLI/Client Adapter）
- [ ] 建立 monorepo 与 CI（format/lint/test）
- [ ] 统一错误码、日志字段、trace_id 规范
- [ ] 统一本地协议 schema（请求/响应/错误）

## 7.2 ALSP（Java）

- [ ] Java Tree-sitter 骨架提取可用
- [ ] Java 符号索引与引用关系可用
- [ ] SQLite + Vector 混合检索可用
- [ ] jdtls definition/reference 打通
- [ ] LSP 失败自动降级静态索引
- [ ] 查询结果返回来源与置信度

## 7.3 ALSP_ADAPTER

- [ ] 完成本地协议服务端口
- [ ] 暴露统一查询 API（scan/map/symbol/refs/goto）
- [ ] 支持超时与限流
- [ ] 可选 MCP 封装可启停

## 7.4 Patchlet

- [ ] SEARCH/REPLACE 解析器完成
- [ ] 原子写与备份恢复完成
- [ ] 冲突检测与错误报告完成
- [ ] 幂等重放测试通过

## 7.5 Orchestrator

- [ ] LangGraph 状态定义完成
- [ ] 节点 I/O schema 完成
- [ ] Analyze/Plan/Execute/Verify/Repair/Done 跑通
- [ ] Build-Check（mvn test）可配置
- [ ] 失败分类与重试上限生效
- [ ] 国际化输出策略生效（中/英）

## 7.6 CLI 与预留 Adapter

- [ ] `task run` 可执行端到端流程
- [ ] `task trace` 可查看节点轨迹与耗时
- [ ] `task replay` 可复现 run
- [ ] `clients/adapter` 预留接口与骨架完成

## 7.7 测试与验收

- [ ] 单元测试（核心模块）
- [ ] 集成测试（端到端主链路）
- [ ] 回归测试（固定 Java fixtures）
- [ ] 性能测试（查询延迟、增量更新）
- [ ] 稳定性测试（长稳、故障注入）

---

## 8. MVP 验收标准（DoD）

- 可在一个中等 Java 仓库稳定完成“定位 -> 修改 -> 验证 -> 输出”闭环。
- 至少 1 类真实缺陷修复任务可重复成功。
- 失败时可明确输出失败节点、错误码、trace_id。
- LSP 不可用时系统仍可降级运行，不中断任务主流程。
- 全链路关键步骤可追踪（输入、工具调用、耗时、结果）。

---

## 9. 推荐目录结构

```text
engine/
  rust/
    alsp/
    alsp_adapter/
    patchlet/
  orchestrator/
    langgraph_orchestrator/
  clients/
    cli/
    adapter/
  fixtures/
    java-sample/
  docs/
```

---

## 10. 近期执行节奏（4 周建议）

### Week 1
- 完成仓库骨架、协议草案、CI、日志与错误码规范。

### Week 2
- 跑通 ALSP（Java Tree-sitter + 索引 + jdtls）。

### Week 3
- 跑通 Patchlet + Orchestrator 主链路。

### Week 4
- 接 CLI，做集成测试、回归测试与 MVP 验收。
