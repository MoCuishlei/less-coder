use anyhow::Result;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

#[derive(Debug, Serialize)]
pub struct RepoMap {
    pub root: String,
    pub language: String,
    pub files: Vec<FileMap>,
}

#[derive(Debug, Serialize, Clone)]
pub struct SymbolLocation {
    pub symbol: String,
    pub file: String,
    pub line: usize,
    pub signature: String,
    pub kind: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct JavaFileCache {
    pub path: String,
    pub modified_unix_ms: u128,
    pub size_bytes: u64,
    pub classes: Vec<ClassSymbol>,
    pub methods: Vec<MethodSymbol>,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct JavaRepoIndexCache {
    pub files: Vec<JavaFileCache>,
}

#[derive(Debug, Serialize, Clone)]
pub struct IncrementalBuildStats {
    pub scanned_files: usize,
    pub reused_files: usize,
    pub rebuilt_files: usize,
}

#[derive(Debug, Serialize)]
pub struct IncrementalRepoMapResult {
    pub map: RepoMap,
    pub cache: JavaRepoIndexCache,
    pub stats: IncrementalBuildStats,
}

#[derive(Debug, Serialize)]
pub struct FileMap {
    pub path: String,
    pub classes: Vec<ClassSymbol>,
    pub methods: Vec<MethodSymbol>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ClassSymbol {
    pub name: String,
    pub signature: String,
    pub line: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MethodSymbol {
    pub name: String,
    pub signature: String,
    pub line: usize,
}

pub fn build_java_repo_map(root: &Path) -> Result<RepoMap> {
    let class_re = Regex::new(r"\b(class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)")?;
    // Minimal Java method signature matcher (non-perfect but sufficient for L1 baseline)
    let method_re = Regex::new(
        r"^\s*(public|protected|private)?\s*(static\s+)?([A-Za-z0-9_<>\[\], ?]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*\{\s*$",
    )?;

    let mut files = Vec::new();
    for entry in WalkDir::new(root).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if !path.is_file() || path.extension().and_then(|s| s.to_str()) != Some("java") {
            continue;
        }

        let content = fs::read_to_string(path)?;
        let mut file_map = FileMap {
            path: to_rel_or_abs(root, path).display().to_string(),
            classes: Vec::new(),
            methods: Vec::new(),
        };

        for (idx, line) in content.lines().enumerate() {
            let lineno = idx + 1;

            if let Some(caps) = class_re.captures(line) {
                let name = caps.get(2).map(|m| m.as_str()).unwrap_or("Unknown");
                file_map.classes.push(ClassSymbol {
                    name: name.to_string(),
                    signature: line.trim().to_string(),
                    line: lineno,
                });
            }

            if let Some(caps) = method_re.captures(line) {
                let method_name = caps.get(4).map(|m| m.as_str()).unwrap_or("unknown");
                // Filter out control flow lines accidentally matching.
                if ["if", "for", "while", "switch", "catch"].contains(&method_name) {
                    continue;
                }
                file_map.methods.push(MethodSymbol {
                    name: method_name.to_string(),
                    signature: line.trim().to_string(),
                    line: lineno,
                });
            }
        }

        if !file_map.classes.is_empty() || !file_map.methods.is_empty() {
            files.push(file_map);
        }
    }

    Ok(RepoMap {
        root: root.display().to_string(),
        language: "java".to_string(),
        files,
    })
}

pub fn build_java_repo_map_incremental(
    root: &Path,
    previous: Option<&JavaRepoIndexCache>,
) -> Result<IncrementalRepoMapResult> {
    let class_re = Regex::new(r"\b(class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)")?;
    let method_re = Regex::new(
        r"^\s*(public|protected|private)?\s*(static\s+)?([A-Za-z0-9_<>\[\], ?]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*\{\s*$",
    )?;

    let mut scanned_files = 0usize;
    let mut reused_files = 0usize;
    let mut rebuilt_files = 0usize;

    let prev_map = previous
        .map(|c| {
            c.files
                .iter()
                .map(|f| (f.path.clone(), f.clone()))
                .collect::<std::collections::HashMap<_, _>>()
        })
        .unwrap_or_default();

    let mut next_cache_files: Vec<JavaFileCache> = Vec::new();
    let mut repo_files: Vec<FileMap> = Vec::new();

    for entry in WalkDir::new(root).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if !path.is_file() || path.extension().and_then(|s| s.to_str()) != Some("java") {
            continue;
        }
        scanned_files += 1;
        let rel = to_rel_or_abs(root, path).display().to_string();
        let meta = fs::metadata(path)?;
        let modified_unix_ms = meta
            .modified()?
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis();
        let size_bytes = meta.len();

        if let Some(prev) = prev_map.get(&rel) {
            if prev.modified_unix_ms == modified_unix_ms && prev.size_bytes == size_bytes {
                reused_files += 1;
                next_cache_files.push(prev.clone());
                repo_files.push(FileMap {
                    path: prev.path.clone(),
                    classes: prev.classes.clone(),
                    methods: prev.methods.clone(),
                });
                continue;
            }
        }

        rebuilt_files += 1;
        let parsed = parse_java_file(path, root, &class_re, &method_re)?;
        next_cache_files.push(JavaFileCache {
            path: parsed.path.clone(),
            modified_unix_ms,
            size_bytes,
            classes: parsed.classes.clone(),
            methods: parsed.methods.clone(),
        });
        repo_files.push(parsed);
    }

    let cache = JavaRepoIndexCache {
        files: next_cache_files,
    };
    let map = RepoMap {
        root: root.display().to_string(),
        language: "java".to_string(),
        files: repo_files,
    };
    let stats = IncrementalBuildStats {
        scanned_files,
        reused_files,
        rebuilt_files,
    };

    Ok(IncrementalRepoMapResult { map, cache, stats })
}

pub fn lookup_java_symbol(root: &Path, symbol: &str) -> Result<Option<SymbolLocation>> {
    let map = build_java_repo_map(root)?;
    for file in map.files {
        for cls in &file.classes {
            if cls.name == symbol {
                return Ok(Some(SymbolLocation {
                    symbol: symbol.to_string(),
                    file: file.path.clone(),
                    line: cls.line,
                    signature: cls.signature.clone(),
                    kind: "class".to_string(),
                }));
            }
        }
        for method in &file.methods {
            if method.name == symbol {
                return Ok(Some(SymbolLocation {
                    symbol: symbol.to_string(),
                    file: file.path.clone(),
                    line: method.line,
                    signature: method.signature.clone(),
                    kind: "method".to_string(),
                }));
            }
        }
    }
    Ok(None)
}

fn to_rel_or_abs(root: &Path, p: &Path) -> PathBuf {
    p.strip_prefix(root).map(|v| v.to_path_buf()).unwrap_or_else(|_| p.to_path_buf())
}

fn parse_java_file(path: &Path, root: &Path, class_re: &Regex, method_re: &Regex) -> Result<FileMap> {
    let content = fs::read_to_string(path)?;
    let mut file_map = FileMap {
        path: to_rel_or_abs(root, path).display().to_string(),
        classes: Vec::new(),
        methods: Vec::new(),
    };
    for (idx, line) in content.lines().enumerate() {
        let lineno = idx + 1;
        if let Some(caps) = class_re.captures(line) {
            let name = caps.get(2).map(|m| m.as_str()).unwrap_or("Unknown");
            file_map.classes.push(ClassSymbol {
                name: name.to_string(),
                signature: line.trim().to_string(),
                line: lineno,
            });
        }
        if let Some(caps) = method_re.captures(line) {
            let method_name = caps.get(4).map(|m| m.as_str()).unwrap_or("unknown");
            if ["if", "for", "while", "switch", "catch"].contains(&method_name) {
                continue;
            }
            file_map.methods.push(MethodSymbol {
                name: method_name.to_string(),
                signature: line.trim().to_string(),
                line: lineno,
            });
        }
    }
    Ok(file_map)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;
    use std::time::Duration;

    #[test]
    fn should_build_repo_map_for_java_fixture() {
        let root = Path::new("../../..").join("fixtures").join("java-sample");
        let map = build_java_repo_map(&root).expect("repo map build failed");
        assert!(!map.files.is_empty());
        let joined = serde_json::to_string(&map).expect("json");
        assert!(joined.contains("NameService"));
        assert!(joined.contains("normalizeName"));
    }

    #[test]
    fn should_lookup_method_symbol_for_java_fixture() {
        let root = Path::new("../../..").join("fixtures").join("java-sample");
        let hit = lookup_java_symbol(&root, "normalizeName")
            .expect("lookup should not fail")
            .expect("symbol should exist");
        assert_eq!(hit.kind, "method");
        assert_eq!(hit.file, r"src\main\java\com\acme\NameService.java");
        assert_eq!(hit.line, 4);
    }

    #[test]
    fn should_lookup_class_symbol_for_java_fixture() {
        let root = Path::new("../../..").join("fixtures").join("java-sample");
        let hit = lookup_java_symbol(&root, "NameService")
            .expect("lookup should not fail")
            .expect("symbol should exist");
        assert_eq!(hit.kind, "class");
        assert_eq!(hit.file, r"src\main\java\com\acme\NameService.java");
        assert_eq!(hit.line, 3);
    }

    #[test]
    fn should_return_none_for_unknown_symbol() {
        let root = Path::new("../../..").join("fixtures").join("java-sample");
        let hit = lookup_java_symbol(&root, "NotExistingSymbol").expect("lookup should not fail");
        assert!(hit.is_none());
    }

    #[test]
    fn should_reuse_unchanged_files_in_incremental_mode() {
        let root = Path::new("../../..").join("fixtures").join("java-sample");
        let first = build_java_repo_map_incremental(&root, None).expect("first build");
        assert!(first.stats.rebuilt_files > 0);
        let second = build_java_repo_map_incremental(&root, Some(&first.cache)).expect("second build");
        assert_eq!(second.stats.rebuilt_files, 0);
        assert!(second.stats.reused_files >= 2);
    }

    #[test]
    fn should_rebuild_changed_file_in_incremental_mode() {
        let temp = tempfile::tempdir().expect("tempdir");
        let root = temp.path().join("java-sample");
        std::fs::create_dir_all(root.join("src/main/java/com/acme")).expect("mkdir");

        let target = root.join("src/main/java/com/acme/NameService.java");
        std::fs::write(
            &target,
            "package com.acme;\npublic class NameService {\npublic String normalizeName(String input) {\nreturn input;\n}\n}\n",
        )
        .expect("write");

        let first = build_java_repo_map_incremental(&root, None).expect("first build");
        assert_eq!(first.stats.rebuilt_files, 1);

        // Ensure fs mtime granularity difference before rewrite.
        thread::sleep(Duration::from_millis(20));
        std::fs::write(
            &target,
            "package com.acme;\npublic class NameService {\npublic String normalizeName(String input) {\nreturn input.trim();\n}\n}\n",
        )
        .expect("rewrite");

        let second = build_java_repo_map_incremental(&root, Some(&first.cache)).expect("second build");
        assert_eq!(second.stats.rebuilt_files, 1);
        assert_eq!(second.stats.reused_files, 0);
    }
}
