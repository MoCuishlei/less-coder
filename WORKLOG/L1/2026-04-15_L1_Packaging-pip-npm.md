# L1 打包任务：pip + npm 可安装 CLI

日期：2026-04-15  
Owner：Python-C / DevOps-A  
状态：完成

## 目标

支持通过包管理器安装并直接运行 `lesscoder`：

- pip 安装后提供 `lesscoder` 命令
- npm 全局安装后提供 `lesscoder` 命令

## Checklist

- [x] 新增 Python 打包元数据（`pyproject.toml`）
- [x] 暴露 `lesscoder` console script
- [x] 新增 npm 包元数据（`package.json`）
- [x] 新增 npm 执行入口（`npm/lesscoder.js`）
- [x] 补充中英文 README（`README.md`, `README_ZH.md`）
- [x] 增加 npm 打包忽略规则（`.npmignore`）
- [x] 验证 pip editable 安装
- [x] 验证 pip 和 npm 入口命令可用
- [x] 验证集成测试全绿

## 验证命令

- `python -m pip install -e .`
- `lesscoder --help`
- `lesscoder server --help`
- `node npm/lesscoder.js --help`
- `npm pack`
- `pytest -q tests/integration`

## 结果

- pip editable 安装成功，`lesscoder` 命令可用。
- npm 打包成功（`lesscoder-cli-0.1.0.tgz`）。
- 集成测试通过（`28 passed`）。

## 备注

- 当前 `lesscoder server` 仍通过 `cargo run` 启动 Rust adapter。
- 若要支持“零 Rust 环境”安装，下一步需发布预编译 adapter 二进制。
