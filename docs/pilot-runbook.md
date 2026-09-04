# Pilot operations runbook

## Scope and ownership

The pilot covers one internal-model team and one third-party ATS user in the EU workspace. The on-call engineer owns availability and rollback; Security owns incident triage; Responsible AI owns metric/release decisions; Legal/DPO owns rule-pack and product-language approval. Candidate-level data is never copied into tickets or chat.

## Start and observe

```bash
docker compose up --build -d
docker compose --profile observability up -d prometheus grafana
curl --fail http://127.0.0.1:8000/v1/health/live
curl --fail http://127.0.0.1:8000/v1/health/ready
```

Prometheus is exposed at `http://127.0.0.1:9090`; the provisioned pilot dashboard is at `http://127.0.0.1:3001`. Change the Grafana password outside local development. Route alerts to the organization's approved paging receiver before launch.

## Pilot data import

Run malware scanning outside FairHire first. In development, the scanner reference may use the explicit `development-scanner:` prefix. Staging/production requires the scanner service's HMAC attestation.

```bash
.venv/bin/python scripts/import_pilot_dataset.py pilot.csv \
  --system-id sys-id \
  --model-version-id model-id \
  --identifier candidate_id \
  --decision selected \
  --timestamp decision_at \
  --protected gender \
  --label qualified \
  --source "Approved ATS export 2026-09" \
  --lawful-basis-ref DPIA-2026-014 \
  --sensitive-attribute-necessity "Aggregate fairness testing approved by DPO" \
  --scanner-reference scanner:scan-id \
  --scanner-attestation signed-value
```

After import, verify the dataset is `ready`, protected fields are `vault_only`, retention has an expiry, and the ledger chain is valid. Do not create an Audit Run if any check fails.

## Alerts and response

### API or dependency outage

1. Acknowledge within 15 minutes and record the affected region/tenant without candidate data.
2. Check `/v1/health/ready` to isolate PostgreSQL, Redis, or object storage.
3. Stop new audit submissions if Redis or object storage is impaired. Do not terminate running workers; cancellation is cooperative.
4. If recovery is not clear within 30 minutes, invoke rollback. Notify pilot owners if the user-visible interruption reaches 60 minutes.

### Elevated API errors

1. Compare 5xx rate by route and the deployment timestamp.
2. Verify database pool health and append-only ledger writes.
3. Roll back if the error ratio remains above 5% for 10 minutes or evidence writes are affected.

### Latency or queue saturation

1. Confirm non-analysis API P95 is above 500 ms and identify the routes.
2. Check worker concurrency, task runtime, and per-tenant queue volume.
3. Pause new work for the noisy tenant before scaling workers. Never increase worker prefetch above one for the pilot.

### Security or evidence-integrity incident

1. Disable new uploads and report exports; preserve logs and object versions.
2. Rotate affected OIDC, scanner, S3, and database credentials through the secret manager.
3. Verify tenant RLS and the event hash chain. Treat a broken chain as a Critical incident.
4. Notify Security and Legal/DPO; follow the approved breach-assessment process.

## Backup and restore drill

Production automation must create encrypted daily PostgreSQL dumps and versioned object-store backups in a separate EU failure domain. Retain backup metadata separately from candidate data. This meets RPO ≤ 24 hours only when the scheduled job and expiry policy are monitored.

For a drill, create a new isolated recovery database and bucket. Never restore over the active pilot environment.

```bash
docker compose exec -T postgres pg_dump --format=custom --no-owner \
  --username fairhire fairhire > artifacts/fairhire-drill.dump

createdb fairhire_restore_drill
pg_restore --exit-on-error --no-owner --dbname fairhire_restore_drill \
  artifacts/fairhire-drill.dump
```

Then verify row counts by tenant, object checksums, a sample report download, and `/v1/audit-events/verify`. Record start/end time, backup timestamp, achieved RPO/RTO, operator, and cleanup reference. The target is RPO ≤ 24h and RTO ≤ 8h.

## Rollout and rollback

1. Deploy the immutable image digest to staging and run the complete Week 14 verification.
2. Back up the database and record the current application image, migration revision, rule pack, and dashboard state.
3. Deploy to the pilot environment with audit submissions disabled; verify liveness, readiness, login, tenant context, ledger writes, and report export.
4. Enable the internal-model tenant, observe for one business day, then enable the third-party ATS tenant.

Rollback triggers include a Critical finding, cross-tenant exposure, event-chain failure, evidence corruption, sustained 5xx/latency breach, or inability to cancel runaway analysis.

Application rollback uses the prior immutable image digest. Database migrations are forward-compatible by policy; do not run Alembic downgrade during an incident. If a schema change is incompatible, deploy a forward repair. Restore data only into an isolated environment first, validate it, then follow the incident commander's approved cutover plan.

## End-of-pilot checklist

- export and freeze the approved evidence package;
- revoke temporary memberships and scanner credentials;
- enforce candidate-data retention deletion and verify backup expiry propagation;
- archive alert, incident, and availability records;
- collect both pilot personas' usability findings without candidate data;
- decide go/no-go with Responsible AI, Security, Engineering, Product, and Legal/DPO.
