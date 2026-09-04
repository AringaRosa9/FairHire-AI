# Week 14 release readiness

This is the evidence index for the FairHire AI pilot release. Automated checks establish technical evidence; named owners must still sign the release in the organization's decision system. A blank approval is a blocker, never an implied approval.

## Release gate matrix

| Gate | Evidence and command | Accountable owner | Technical status | Approval reference |
|---|---|---|---|---|
| Three known bias patterns | `tests/benchmark/test_known_bias_datasets.py`; `.venv/bin/pytest tests/benchmark/test_known_bias_datasets.py` | Responsible AI lead | Automated | Required |
| Independent metric cross-check | Direct count formulas in the benchmark test | Data science lead | Automated | Required |
| 1M rows / 50 features under 20 minutes | `tests/benchmark/benchmark_million_rows.py`; sample evidence: `docs/evidence/week14-million-row-benchmark.json` | Data engineering lead | Passed in 66.755s on recorded development host; environment rerun required | Required |
| Locked-environment reproducibility | `uv.lock`, `package-lock.json`, deterministic seed tests, CI build | Engineering lead | Automated | Required |
| Tenant isolation and authorization | `tests/security/test_postgres_rls.py`, `apps/api/tests/test_api.py` | Security lead | Automated; PostgreSQL test requires service | Required |
| Malicious upload and signed URL controls | `tests/security/test_application_security.py`, worker upload tests | Security lead | Automated | Required |
| Prompt injection and project-evidence filtering | `test_assistant_filters_sources_cites_paragraphs_and_records_injection` | AI security lead | Automated | Required |
| No unsafe customer model execution | Pickle/Joblib API and worker rejection tests; worker has no model loader | Security lead | Automated | Required |
| Critical/evidence-gap/expired-rule release blocking | Governance API tests and Release Gate blockers | Responsible AI lead | Automated | Required |
| WCAG 2.2 AA and keyboard path | axe and skip-link Playwright checks | Accessibility owner | Automated plus manual screen-reader sample | Required |
| Responsive, browser, bilingual regression | Chromium, Firefox, WebKit and mobile Playwright projects | QA lead | Automated | Required |
| Dependency scan / SBOM | CI runs npm and Python advisory scans; `npm run sbom` creates Node and Python CycloneDX files | Security lead | Automated; local npm mirror lacks advisory API | Required |
| Backup restore and rollback drill | `docs/pilot-runbook.md` drill record | SRE/on-call lead | Manual drill required | Required |
| External claims and legal wording | Product copy review; risk-evidence disclaimer regression | Legal/DPO | Manual review required | Required |

## One-command verification

```bash
npm run verify:week14
```

Browser and million-row checks are opt-in because they install/use browser runtimes and consume more time:

```bash
FAIRHIRE_RUN_E2E=1 FAIRHIRE_RUN_LOAD_TEST=1 npm run verify:week14
```

The run is release evidence only when the CI commit SHA, environment, timestamps, output artifacts, and approval references are attached to the release record.

## Mandatory stop conditions

Do not start or continue the pilot if any of these are true:

- any Critical security or governance finding is open without a valid, time-limited exception;
- the latest audit contains `insufficient_evidence` metrics;
- the latest audit uses a rule pack other than the organization's current version;
- `policy_pack_expires_at` is in the past;
- the append-only event ledger fails verification;
- backup restoration has not been demonstrated within the RTO/RPO;
- Legal/DPO has not approved the external wording.

The API enforces the first four conditions in the Release Gate. The remaining conditions are deployment gates owned by the release process.
