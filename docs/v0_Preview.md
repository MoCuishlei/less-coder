# v0_Preview 更新（L0）

更新时间：2026-04-14

## 本次完成

- 已建立 3 条集成测试用例骨架：
  - 正常链路：`Analyze -> Plan -> Execute -> Verify -> Done`
  - LSP 降级：模拟 `ALSP_LSP_TIMEOUT`，确认回退后流程可达 `Done`
  - 补丁冲突：模拟 `PATCHLET_CONFLICT`，确认进入 `Repair`
- 已接入 CI（GitHub Actions）：
  - 自动运行 `pytest -q tests/integration`

## 文件清单

- `tests/integration/test_protocol_v0_preview.py`
- `.github/workflows/ci.yml`

## 说明

- 当前为 L0 骨架测试，使用模拟结果验证状态机路由和错误码约束。
- L1 阶段将把模拟替换为真实本地协议调用（ALSP_ADAPTER / Patchlet / Orchestrator）。
