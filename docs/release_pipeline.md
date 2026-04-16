# Release Pipeline

## Trigger

- Auto: push tag matching `v*`
- Manual: GitHub Actions `Release` workflow dispatch

## Recommended Pre-Tag Dry Run

Run this before creating tag:

```bash
lesscoder release-dry-run --project-root /abs/path/to/less-coder --tag v0.1.0
```

What it validates:

- Python and npm versions are aligned (`pyproject.toml` vs `package.json`)
- Optional tag format/version match (`vMAJOR.MINOR.PATCH`)
- Integration tests (`pytest -q tests/integration`)
- Python package build (`python -m build`)
- npm package pack (`npm pack`)
- Rust adapter release build (`cargo build --release`)

Use `--skip-tests` only when CI already ran the same commit:

```bash
lesscoder release-dry-run --project-root /abs/path/to/less-coder --skip-tests
```

## CI Release Jobs (`.github/workflows/release.yml`)

1. Verify integration tests
2. Build Python distributions
3. Pack npm tarball
4. Build Rust adapter binaries (Linux/Windows/macOS)
   - `alsp_adapter_windows_x86_64.exe`
   - `alsp_adapter_linux_x86_64`
   - `alsp_adapter_macos_x86_64`
   - plus `lesscoder_adapter_manifest.json` (sha256 checksums)
5. Create GitHub Release for tag events
6. Publish to PyPI/npm if secrets are configured

## Required Secrets

- `PYPI_API_TOKEN`
- `NPM_TOKEN`
