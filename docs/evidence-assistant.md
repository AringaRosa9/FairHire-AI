# Evidence packages and read-only assistant

## Evidence package lifecycle

`POST /v1/reports` accepts an AI System and a succeeded Audit Run. The API takes a deterministic snapshot of the seven required sections and builds an evidence index in which every Metric Result keeps its Audit Run ID, metric ID, value, method, and calculation version. The canonical snapshot is hashed with SHA-256.

Reports are append-only versions. Creating a later draft points to the preceding version. Approving a draft marks any previous approved version for that system as `superseded`; neither the frozen sections nor their hash is edited. Drafts with unresolved Evidence Gaps cannot be approved.

`GET /v1/reports/{id}/diff` compares the frozen structured snapshots. `GET /v1/reports/{id}/download?format=pdf|json|csv` exports the dossier or metric provenance ledger and records the export in the append-only audit ledger.

## Knowledge sources

Policy administrators register versioned sources through `POST /v1/knowledge-sources`. Each source records its publisher, canonical URI, jurisdiction, version, effective date, review date, content hash, and optional role allowlist. List and retrieval paths apply organization and role filters before returning source content.

Official and organization-policy text is always treated as untrusted evidence. It cannot introduce instructions or tools into the assistant runtime.

## Assistant safety contract

`POST /v1/assistant/answers` is read-only with respect to project state. It can retrieve only:

- authorized official and organization-policy sources;
- the selected AI System record;
- frozen report and aggregate Audit Run references available to the current organization.

It does not retrieve candidate-level data or raw resumes. Answers label every paragraph as `fact`, `inference`, or `recommendation`; substantive paragraphs cite source IDs, and rule citations carry effective and review dates. If evidence is absent, the response states the gap instead of making a legal conclusion.

Instruction-override patterns are detected before retrieval output is composed. The attempt, citation set, project evidence references, actor, and final answer are written to `assistant_answers` and the hash-chained audit event ledger.
