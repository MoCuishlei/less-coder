use anyhow::Result;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::path::PathBuf;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::{TcpListener, TcpStream};

#[derive(Debug, Deserialize)]
struct RequestEnvelope {
    version: String,
    request_id: String,
    trace_id: String,
    #[allow(dead_code)]
    session_id: Option<String>,
    #[allow(dead_code)]
    source: String,
    #[allow(dead_code)]
    target: String,
    action: String,
    #[allow(dead_code)]
    payload: Value,
    #[allow(dead_code)]
    meta: Option<Value>,
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

#[tokio::main]
async fn main() -> Result<()> {
    // L0-P0-01 baseline: TCP localhost transport.
    let addr = std::env::var("ALSP_ADAPTER_ADDR").unwrap_or_else(|_| "127.0.0.1:8787".to_string());
    let listener = TcpListener::bind(&addr).await?;
    println!("alsp_adapter listening on {addr}");

    loop {
        let (socket, peer) = listener.accept().await?;
        tokio::spawn(async move {
            if let Err(err) = handle_connection(socket).await {
                eprintln!("connection error from {peer}: {err}");
            }
        });
    }
}

async fn handle_connection(socket: TcpStream) -> Result<()> {
    let (reader, mut writer) = socket.into_split();
    let mut lines = BufReader::new(reader).lines();

    while let Some(line) = lines.next_line().await? {
        if line.trim().is_empty() {
            continue;
        }

        let response = match serde_json::from_str::<RequestEnvelope>(&line) {
            Ok(req) => handle_request(req),
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
                cost: json!({ "duration_ms": 0 }),
            },
        };

        let payload = serde_json::to_string(&response)?;
        writer.write_all(payload.as_bytes()).await?;
        writer.write_all(b"\n").await?;
        writer.flush().await?;
    }

    Ok(())
}

fn handle_request(req: RequestEnvelope) -> ResponseEnvelope {
    if req.version != "v0" {
        return ResponseEnvelope {
            version: "v0".to_string(),
            request_id: req.request_id,
            trace_id: req.trace_id,
            status: "error".to_string(),
            data: None,
            error: Some(ErrorBody {
                code: "COMMON_BAD_REQUEST".to_string(),
                message: format!("unsupported version: {}", req.version),
                retryable: false,
                node: "Adapter".to_string(),
                details: json!({ "supported_version": "v0" }),
            }),
            fallback_used: false,
            cost: json!({ "duration_ms": 0 }),
        };
    }

    route_action(req)
}

fn route_action(req: RequestEnvelope) -> ResponseEnvelope {
    match req.action.as_str() {
        "repo.map" => {
            let root = extract_root_path(&req.payload).unwrap_or_else(|| ".".to_string());
            let root_path = PathBuf::from(&root);
            match alsp::build_java_repo_map(&root_path) {
                Ok(map) => ok_response(req, serde_json::to_value(map).unwrap_or(json!({}))),
                Err(err) => internal_error_response(req, "COMMON_INTERNAL", format!("repo.map failed: {err}")),
            }
        }
        "symbol.lookup" | "symbol.lookup.static" => {
            let root = extract_root_path(&req.payload).unwrap_or_else(|| ".".to_string());
            let symbol = req.payload.get("symbol").and_then(|v| v.as_str()).map(|s| s.to_string());
            let Some(symbol) = symbol else {
                return bad_request_response(req, "missing payload.symbol");
            };
            if req.action == "symbol.lookup"
                && req
                    .payload
                    .get("force_lsp_timeout")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false)
            {
                return error_response(
                    req,
                    "ALSP_LSP_TIMEOUT",
                    "simulated lsp timeout",
                    true,
                    "Analyze",
                    json!({"symbol": symbol}),
                );
            }
            match alsp::lookup_java_symbol(&PathBuf::from(&root), &symbol) {
                Ok(Some(loc)) => ok_response(req, serde_json::to_value(loc).unwrap_or(json!({}))),
                Ok(None) => error_response(
                    req,
                    "ALSP_SYMBOL_NOT_FOUND",
                    "symbol not found",
                    false,
                    "Analyze",
                    json!({"symbol": symbol}),
                ),
                Err(err) => internal_error_response(req, "COMMON_INTERNAL", format!("symbol.lookup failed: {err}")),
            }
        }
        "patch.apply" => {
            let target = req
                .payload
                .get("target")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
            let Some(target) = target else {
                return bad_request_response(req, "missing payload.target");
            };
            let block = req
                .payload
                .get("search_replace_blocks")
                .and_then(|v| v.as_array())
                .and_then(|arr| arr.first())
                .cloned();
            let Some(block) = block else {
                return bad_request_response(req, "missing payload.search_replace_blocks[0]");
            };
            let search = block.get("search").and_then(|v| v.as_str()).unwrap_or("");
            let replace = block.get("replace").and_then(|v| v.as_str()).unwrap_or("");
            let force_conflict = req
                .payload
                .get("force_patch_conflict")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            if search.is_empty() {
                return bad_request_response(req, "empty search pattern");
            }
            if force_conflict {
                return error_response(
                    req,
                    "PATCHLET_CONFLICT",
                    "simulated patch conflict",
                    false,
                    "Execute",
                    json!({"file": target, "search_excerpt": search}),
                );
            }

            match patchlet::apply_search_replace_with_backup(PathBuf::from(&target).as_path(), search, replace) {
                Ok(result) => {
                    if result.replacements == 0 {
                        error_response(
                            req,
                            "PATCHLET_SEARCH_MISS",
                            "search block not found in target file",
                            false,
                            "Execute",
                            json!({"file": target, "search_excerpt": search}),
                        )
                    } else {
                        ok_response(req, serde_json::to_value(result).unwrap_or(json!({})))
                    }
                }
                Err(err) => error_response(
                    req,
                    "PATCHLET_APPLY_FAILED",
                    &format!("patch apply failed: {err}"),
                    true,
                    "Execute",
                    json!({"file": target, "search_excerpt": search}),
                ),
            }
        }
        _ => error_response(
            req,
            "ADAPTER_ROUTE_FAILED",
            "unsupported action",
            true,
            "Adapter",
            json!({}),
        ),
    }
}

fn extract_root_path(payload: &Value) -> Option<String> {
    payload
        .get("path")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .or_else(|| {
            payload
                .get("project_root")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
        })
}

fn ok_response(req: RequestEnvelope, data: Value) -> ResponseEnvelope {
    ResponseEnvelope {
        version: "v0".to_string(),
        request_id: req.request_id,
        trace_id: req.trace_id,
        status: "ok".to_string(),
        data: Some(data),
        error: None,
        fallback_used: false,
        cost: json!({ "duration_ms": 1 }),
    }
}

fn bad_request_response(req: RequestEnvelope, message: &str) -> ResponseEnvelope {
    error_response(
        req,
        "COMMON_BAD_REQUEST",
        message,
        false,
        "Adapter",
        json!({}),
    )
}

fn internal_error_response(req: RequestEnvelope, code: &str, message: String) -> ResponseEnvelope {
    error_response(req, code, &message, true, "Adapter", json!({}))
}

fn error_response(
    req: RequestEnvelope,
    code: &str,
    message: &str,
    retryable: bool,
    node: &str,
    details: Value,
) -> ResponseEnvelope {
    ResponseEnvelope {
        version: "v0".to_string(),
        request_id: req.request_id,
        trace_id: req.trace_id,
        status: "error".to_string(),
        data: None,
        error: Some(ErrorBody {
            code: code.to_string(),
            message: message.to_string(),
            retryable,
            node: node.to_string(),
            details,
        }),
        fallback_used: false,
        cost: json!({ "duration_ms": 0 }),
    }
}
