#!/usr/bin/env bash
set -euo pipefail

artifact_dir="${FAIRHIRE_EVIDENCE_DIR:-artifacts/release-evidence}"
mkdir -p "$artifact_dir"

npm run lint
npm run typecheck
npm test
npm run build
.venv/bin/ruff check apps/api apps/worker python tests
.venv/bin/mypy apps/api/fairhire_api python/fairhire_domain/fairhire_domain
.venv/bin/pytest
bash scripts/generate_sbom.sh "$artifact_dir/sbom"

if [[ "${FAIRHIRE_RUN_E2E:-0}" == "1" ]]; then
  npm run test:e2e
fi

if [[ "${FAIRHIRE_RUN_LOAD_TEST:-0}" == "1" ]]; then
  .venv/bin/python tests/benchmark/benchmark_million_rows.py \
    --output "$artifact_dir/million-row-benchmark.json"
fi

printf 'Week 14 automated verification passed. Evidence: %s\n' "$artifact_dir"
