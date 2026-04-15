# L0 协议评审记录（本地协议 v0）

## 基本信息
- 日期：2026-04-14
- 主题：本地协议 v0（请求/响应/错误码/trace_id）评审
- 参与模块：`ALSP / ALSP_ADAPTER / Orchestrator / Patchlet / CLI`

## 评审输入
- 协议文档：`docs/local_protocol_v0.md`
- 评审目标：
  - 冻结 v0 通用结构
  - 冻结错误码基线
  - 冻结 trace_id 透传规范

## 评审结论
- 结论：`全部通过（v0-frozen）`
- 通过项：
  - 请求/响应结构统一
  - 错误对象与错误码命名规则明确
  - trace_id 生命周期与透传规则明确
  - action 最小集覆盖 Java MVP 主链路

## 评审后处理
- 已确认项：
  - 本地协议 v0 作为当前联调基线生效
  - 错误码基线与重试语义可直接用于 Orchestrator 路由
  - trace_id 规范可直接用于日志与链路追踪
  - 本地传输首选 `TCP 127.0.0.1`，Named Pipe / Unix Socket 为后续优化回退
  - `checks.run` 沙箱字段与安全规则已固化
  - `PATCHLET_APPLY_FAILED` / `PATCHLET_CONFLICT` 样例响应已补充
  - 集成测试基线 3 用例已定义（正常、LSP 降级、补丁冲突）
- 后续项（非阻塞，转实现阶段）：
  - 按基线实现联调与自动化测试

## 风险
- 若本周不完成传输实现选型，Orchestrator 与 Rust 联调将推迟。
- 若错误码与重试策略不绑定，Repair 节点收敛性不足。

## 下一步
- [ ] 输出实现任务拆分（Owner + 截止时间）
- [ ] 建立 3 条集成测试用例骨架并接入 CI
