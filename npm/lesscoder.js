#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");
const args = process.argv.slice(2);

function runPython(cmd, cmdArgs) {
  return spawnSync(cmd, cmdArgs, {
    cwd: repoRoot,
    stdio: "inherit",
    env: process.env,
    shell: false,
  });
}

function main() {
  const preferred = process.env.LESSCODER_PYTHON;
  const candidates = preferred
    ? [[preferred, ["-m", "clients.cli.lesscoder", ...args]]]
    : process.platform === "win32"
      ? [
          ["python", ["-m", "clients.cli.lesscoder", ...args]],
          ["py", ["-3", "-m", "clients.cli.lesscoder", ...args]],
        ]
      : [["python3", ["-m", "clients.cli.lesscoder", ...args]], ["python", ["-m", "clients.cli.lesscoder", ...args]]];

  for (const [cmd, cmdArgs] of candidates) {
    const result = runPython(cmd, cmdArgs);
    if (!result.error) {
      process.exit(typeof result.status === "number" ? result.status : 0);
    }
  }

  process.stderr.write(
    "lesscoder: Python 3.11+ not found. Install Python and retry, or set LESSCODER_PYTHON.\n"
  );
  process.exit(127);
}

main();
