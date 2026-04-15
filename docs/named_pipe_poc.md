# L0-P1-01 Named Pipe PoC（Windows）

## 目标

验证 `ALSP_ADAPTER` 可通过 Windows Named Pipe 提供本地协议服务端能力（PoC）。

## 启动

在项目根目录执行：

```powershell
cargo run --manifest-path engine/rust/alsp_adapter/Cargo.toml --bin named_pipe_poc
```

可选自定义管道名：

```powershell
$env:ALSP_ADAPTER_PIPE="\\.\pipe\alsp_adapter_v0"; cargo run --manifest-path engine/rust/alsp_adapter/Cargo.toml --bin named_pipe_poc
```

## 协议行为

- 输入：每行一个 JSON 请求（与 `v0` 请求结构一致）
- 输出：每行一个 JSON 响应
- 成功响应 `data.transport = "named_pipe"`

## 说明

- 该实现为 PoC，不替代当前 TCP 主通道。
- 当前主通道仍是 `TCP 127.0.0.1`，Named Pipe 作为 Windows 优化回退路径。
