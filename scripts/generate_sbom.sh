#!/usr/bin/env bash
set -euo pipefail

artifact_dir="${1:-artifacts/sbom}"
mkdir -p "$artifact_dir"
# Platform-specific optional native packages are intentionally absent from npm's local tree.
npm sbom --package-lock-only --omit=optional --sbom-format cyclonedx > "$artifact_dir/node.cdx.json"
UV_CACHE_DIR="${TMPDIR:-/tmp}/fairhire-uv-cache" \
  uv --preview-features sbom-export export --locked --all-packages \
  --format cyclonedx1.5 --output-file "$artifact_dir/python.cdx.json" >/dev/null
printf 'SBOMs written to %s\n' "$artifact_dir"
