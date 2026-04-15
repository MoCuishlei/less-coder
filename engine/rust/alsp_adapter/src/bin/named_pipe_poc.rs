use anyhow::Result;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

#[cfg(windows)]
use tokio::net::windows::named_pipe::{NamedPipeServer, ServerOptions};

#[derive(Debug, Deserialize)]
struct RequestEnvelope {
    version: String,
    request_id: String,
    trace_id: String,
    action: String,
    #[allow(dead_code)]
    payload: Value,
}

#[derive(Debug, Serialize)]
struct ErrorBody {
    code: String,
    message: String,
    retryable: bool,
    node: String,
    details: Value,
}

#[derive(Debug, Serialize)]
struct ResponseEnvelope {
    version: String,
    request_id: String,
    trace_id: String,
    status: String,
    data: Option<Value>,
    error: Option<ErrorBody>,
    fallback_used: bool,
    cost: Value,
}

#[cfg(windows)]
#[tokio::main]
async fn main() -> Result<()> {
    let pipe_name = std::env::var("ALSP_ADAPTER_PIPE")
        .unwrap_or_else(|_| r"\\.\pipe\alsp_adapter_v0".to_string());
    println!("named-pipe poc listening on {pipe_name}");

    loop {
        let server = ServerOptions::new().create(&pipe_name)?;
        server.connect().await?;
        tokio::spawn(async move {
            if let Err(err) = handle_client(server).await {
                eprintln!("pipe client error: {err}");
            }
        });
    }
}

#[cfg(windows)]
async fn handle_client(server: NamedPipeServer) -> Result<()> {
    let (reader, mut writer) = tokio::io::split(server);
    let mut lines = BufReader::new(reader).lines();

    while let Some(line) = lines.next_line().await? {
        if line.trim().is_empty() {
            continue;
        }
        let response = match serde_json::from_str::<RequestEnvelope>(&line) {
            Ok(req) => {
                if req.version != "v0" {
                    ResponseEnvelope {
                        version: "v0".to_string(),
                        request_id: req.request_id,
                        trace_id: req.trace_id,
                        status: "error".to_string(),
                        data: None,
                        error: Some(ErrorBody {
                            code: "COMMON_BAD_REQUEST".to_string(),
                            message: "unsupported version".to_string(),
                            retryable: false,
                            node: "Adapter".to_string(),
                            details: json!({"supported_version": "v0"}),
                        }),
                        fallback_used: false,
                        cost: json!({"duration_ms": 0}),
                    }
                } else {
                    ResponseEnvelope {
                        version: "v0".to_string(),
                        request_id: req.request_id,
                        trace_id: req.trace_id,
                        status: "ok".to_string(),
                        data: Some(json!({
                            "accepted": true,
                            "action": req.action,
                            "transport": "named_pipe",
                            "adapter": "alsp_adapter"
                        })),
                        error: None,
                        fallback_used: false,
                        cost: json!({"duration_ms": 1}),
                    }
                }
            }
            Err(err) => ResponseEnvelope {
                version: "v0".to_string(),
                request_id: "unknown".to_string(),
                trace_id: "unknown".to_string(),
                status: "error".to_string(),
                data: None,
                error: Some(ErrorBody {
                    code: "COMMON_BAD_REQUEST".to_string(),
                    message: format!("invalid json request: {err}"),
                    retryable: false,
                    node: "Adapter".to_string(),
                    details: json!({}),
                }),
                fallback_used: false,
                cost: json!({"duration_ms": 0}),
            },
        };

        let raw = serde_json::to_string(&response)?;
        writer.write_all(raw.as_bytes()).await?;
        writer.write_all(b"\n").await?;
        writer.flush().await?;
    }
    Ok(())
}

#[cfg(not(windows))]
fn main() {
    eprintln!("named_pipe_poc is only supported on Windows.");
}
