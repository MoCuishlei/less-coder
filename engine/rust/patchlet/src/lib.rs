use serde::Serialize;
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct ErrorBody {
    pub code: String,
    pub message: String,
    pub retryable: bool,
    pub node: String,
    pub details: Value,
}

#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct ResponseEnvelope {
    pub version: String,
    pub request_id: String,
    pub trace_id: String,
    pub status: String,
    pub data: Option<Value>,
    pub error: Option<ErrorBody>,
    pub fallback_used: bool,
}

#[derive(Debug, Clone)]
pub struct PatchContext<'a> {
    pub request_id: &'a str,
    pub trace_id: &'a str,
    pub file: &'a str,
    pub line: u32,
    pub search_excerpt: &'a str,
}

#[derive(Debug, Serialize, Clone)]
pub struct PatchApplyResult {
    pub target_file: String,
    pub backup_file: String,
    pub replacements: usize,
}

pub fn patchlet_apply_failed(ctx: PatchContext<'_>, message: &str) -> ResponseEnvelope {
    ResponseEnvelope {
        version: "v0".to_string(),
        request_id: ctx.request_id.to_string(),
        trace_id: ctx.trace_id.to_string(),
        status: "error".to_string(),
        data: None,
        error: Some(ErrorBody {
            code: "PATCHLET_APPLY_FAILED".to_string(),
            message: message.to_string(),
            retryable: true,
            node: "Execute".to_string(),
            details: json!({
                "file": ctx.file,
                "line": ctx.line,
                "search_excerpt": ctx.search_excerpt
            }),
        }),
        fallback_used: false,
    }
}

pub fn patchlet_conflict(ctx: PatchContext<'_>, message: &str) -> ResponseEnvelope {
    ResponseEnvelope {
        version: "v0".to_string(),
        request_id: ctx.request_id.to_string(),
        trace_id: ctx.trace_id.to_string(),
        status: "error".to_string(),
        data: None,
        error: Some(ErrorBody {
            code: "PATCHLET_CONFLICT".to_string(),
            message: message.to_string(),
            retryable: false,
            node: "Execute".to_string(),
            details: json!({
                "file": ctx.file,
                "line": ctx.line,
                "search_excerpt": ctx.search_excerpt
            }),
        }),
        fallback_used: false,
    }
}

pub fn apply_search_replace_with_backup(
    target_file: &Path,
    search: &str,
    replace: &str,
) -> std::io::Result<PatchApplyResult> {
    let original = fs::read_to_string(target_file)?;
    let matches = original.match_indices(search).count();
    if matches == 0 {
        return Ok(PatchApplyResult {
            target_file: target_file.display().to_string(),
            backup_file: String::new(),
            replacements: 0,
        });
    }

    let backup_file = backup_path_for(target_file);
    fs::write(&backup_file, &original)?;

    let updated = original.replace(search, replace);
    fs::write(target_file, updated)?;

    Ok(PatchApplyResult {
        target_file: target_file.display().to_string(),
        backup_file: backup_file.display().to_string(),
        replacements: matches,
    })
}

pub fn rollback_from_backup(target_file: &Path, backup_file: &Path) -> std::io::Result<()> {
    let backup_content = fs::read_to_string(backup_file)?;
    fs::write(target_file, backup_content)?;
    Ok(())
}

fn backup_path_for(target_file: &Path) -> PathBuf {
    let name = target_file
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("unknown_file");
    target_file.with_file_name(format!("{name}.patchlet.bak"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn sample_ctx() -> PatchContext<'static> {
        PatchContext {
            request_id: "req_01",
            trace_id: "tr_01",
            file: "src/main/java/com/acme/A.java",
            line: 42,
            search_excerpt: "if (x == null) {",
        }
    }

    #[test]
    fn apply_failed_should_be_retryable() {
        let resp = patchlet_apply_failed(sample_ctx(), "transient io error");
        let err = resp.error.expect("error must exist");
        assert_eq!(err.code, "PATCHLET_APPLY_FAILED");
        assert!(err.retryable);
        assert_eq!(err.details["file"], "src/main/java/com/acme/A.java");
        assert_eq!(err.details["line"], 42);
        assert_eq!(err.details["search_excerpt"], "if (x == null) {");
    }

    #[test]
    fn conflict_should_not_be_retryable() {
        let resp = patchlet_conflict(sample_ctx(), "ambiguous search match");
        let err = resp.error.expect("error must exist");
        assert_eq!(err.code, "PATCHLET_CONFLICT");
        assert!(!err.retryable);
        assert_eq!(err.details["file"], "src/main/java/com/acme/A.java");
        assert_eq!(err.details["line"], 42);
        assert_eq!(err.details["search_excerpt"], "if (x == null) {");
    }

    fn tmp_file_path(tag: &str) -> std::path::PathBuf {
        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir().join(format!("patchlet_{tag}_{ts}.txt"))
    }

    #[test]
    fn apply_search_replace_should_create_backup_and_modify_file() {
        let target = tmp_file_path("apply");
        std::fs::write(&target, "hello old world").expect("write target");

        let result = apply_search_replace_with_backup(&target, "old", "new").expect("apply patch");
        assert_eq!(result.replacements, 1);
        assert!(!result.backup_file.is_empty());

        let updated = std::fs::read_to_string(&target).expect("read updated");
        assert_eq!(updated, "hello new world");

        let backup = std::fs::read_to_string(result.backup_file).expect("read backup");
        assert_eq!(backup, "hello old world");
    }

    #[test]
    fn rollback_should_restore_original_content() {
        let target = tmp_file_path("rollback");
        std::fs::write(&target, "line old").expect("write target");
        let result = apply_search_replace_with_backup(&target, "old", "new").expect("apply patch");
        let backup_path = std::path::PathBuf::from(result.backup_file);

        rollback_from_backup(&target, &backup_path).expect("rollback");
        let restored = std::fs::read_to_string(&target).expect("read restored");
        assert_eq!(restored, "line old");
    }
}
