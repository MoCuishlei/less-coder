# L0-P1-02 Unix Socket PoC（Linux/macOS）

## 目标

验证 `ALSP_ADAPTER` 可通过 Unix Socket 提供本地协议服务端能力（PoC）。

## 启动

在项目根目录执行：

```bash
cargo run --manifest-path engine/rust/alsp_adapter/Cargo.toml --bin unix_socket_poc
```

可选自定义 socket 路径：

```bash
ALSP_ADAPTER_SOCK=/tmp/alsp_adapter_v0.sock cargo run --manifest-path engine/rust/alsp_adapter/Cargo.toml --bin unix_socket_poc
```

## 协议行为

- 输入：每行一个 JSON 请求（与 `v0` 请求结构一致）
- 输出：每行一个 JSON 响应
- 成功响应 `data.transport = "unix_socket"`

## 说明

- 该实现为 PoC，不替代当前 TCP 主通道。
- 当前主通道仍是 `TCP 127.0.0.1`，Unix Socket 作为 Linux/macOS 优化回退路径。
