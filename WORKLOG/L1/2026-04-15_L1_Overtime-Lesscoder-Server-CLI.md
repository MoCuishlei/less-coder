# L1 加班任务：lesscoder Server/CLI 统一入口

日期：2026-04-15  
Owner：Python-C / Rust-B  
状态：完成

## 目标

统一用户入口命令为 `lesscoder`：

- `lesscoder`：CLI 任务模式
- `lesscoder server`：本地服务模式（MCP-ready 入口）

## Checklist

- [x] 在统一 CLI 中加入 `server` 子命令
- [x] 增加 `clients.cli.lesscoder` 入口模块
- [x] 增加 Windows 启动脚本 `lesscoder.cmd`
- [x] 保持原 `task_cli` 的 run/trace 兼容
- [x] 增加统一入口的集成测试
- [x] 本地验证命令行为

## 实现内容

- 更新 `clients/cli/task_cli.py`
  - 统一子命令：`run` / `trace` / `server`
  - `server` 通过 `cargo run` 启动 `alsp_adapter` 并注入 `ALSP_ADAPTER_ADDR`
- 新增 `clients/cli/lesscoder.py`
  - 提供统一 `lesscoder` 命令入口
- 新增 `lesscoder.cmd`
  - `python -m clients.cli.lesscoder %*`
- 新增测试 `tests/integration/test_lesscoder_entrypoint.py`

## 验证命令

- `python -m clients.cli.lesscoder --help`
- `python -m clients.cli.lesscoder server --help`
- `.\lesscoder.cmd --help`
- `pytest -q tests/integration/test_cli_task_run.py tests/integration/test_lesscoder_entrypoint.py`

结果：通过（4 passed）

## 备注

- 实现了双终端运行模型：
  - 终端 A：`lesscoder server`
  - 终端 B：`lesscoder run/trace`
- 下一步可选：提供独立安装器/console-script，支持全局命令开箱即用。
