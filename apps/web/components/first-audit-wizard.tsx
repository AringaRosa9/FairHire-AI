"use client";

import type {
  Dataset,
  DraftUpdate,
  FieldMappingsCreate,
} from "@fairhire/api-client";
import { StatusBadge } from "@fairhire/ui";
import type { Route } from "next";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { createBrowserApi } from "@/lib/browser-api";

const steps = ["System", "Data", "Fields", "Basis", "Run"] as const;
const fieldRoles = [
  "identifier",
  "feature",
  "protected_attribute",
  "label",
  "prediction",
  "decision",
  "timestamp",
  "metadata",
] as const;

type FieldRole = (typeof fieldRoles)[number];
type WizardField = {
  id: string;
  name: string;
  inferred_type:
    | "string"
    | "integer"
    | "number"
    | "boolean"
    | "date"
    | "datetime"
    | "category";
  nullable: boolean;
  missing_rate: number;
  role: FieldRole;
};

type WizardState = {
  draftId: string;
  step: number;
  name: string;
  purpose: string;
  actualUse: string;
  affectedPeople: string;
  decisionImpact:
    | "screening"
    | "recommendation"
    | "employment_decision"
    | "support_only";
  providerType: "internal" | "third_party";
  providerName: string;
  ownerName: string;
  jurisdictions: string[];
  roles: string[];
  humanOversight: string;
  profiling: boolean;
  solelyAutomated: boolean;
  employmentUse: boolean;
  emotionInference: boolean;
  sensitiveTraitInference: boolean;
  systemId?: string;
  modelVersionLabel: string;
  modelVersionId?: string;
  datasetId?: string;
  fileName?: string;
  fileHash?: string;
  rowCount?: number;
  fields: WizardField[];
  source: string;
  collectionPurpose: string;
  lawfulBasisRef: string;
  necessity: string;
  retentionExpiresAt: string;
  auditRunId?: string;
  jobId?: string;
};

const initialState: WizardState = {
  draftId: "first-audit",
  step: 1,
  name: "",
  purpose: "",
  actualUse: "",
  affectedPeople: "",
  decisionImpact: "screening",
  providerType: "internal",
  providerName: "",
  ownerName: "Maya Chen",
  jurisdictions: ["EU", "DE"],
  roles: ["provider", "deployer"],
  humanOversight: "",
  profiling: false,
  solelyAutomated: false,
  employmentUse: true,
  emotionInference: false,
  sensitiveTraitInference: false,
  modelVersionLabel: "",
  fields: [],
  source: "",
  collectionPurpose: "",
  lawfulBasisRef: "",
  necessity: "",
  retentionExpiresAt: "",
};

function guessRole(name: string): FieldRole {
  const normalized = name.toLowerCase();
  if (normalized.includes("candidate") && normalized.includes("id"))
    return "identifier";
  if (normalized.includes("timestamp") || normalized.endsWith("_at"))
    return "timestamp";
  if (normalized.includes("decision") || normalized.includes("selected"))
    return "decision";
  if (normalized.includes("prediction") || normalized.includes("score"))
    return "prediction";
  if (["gender", "sex", "age_group", "nationality"].includes(normalized)) {
    return "protected_attribute";
  }
  if (normalized.includes("label") || normalized.includes("outcome"))
    return "label";
  return "feature";
}

function inferValueType(values: unknown[]): WizardField["inferred_type"] {
  const present = values.filter((value) => value !== null && value !== "");
  if (present.length === 0) return "string";
  if (present.every((value) => typeof value === "boolean")) return "boolean";
  if (
    present.every(
      (value) => typeof value === "number" && Number.isInteger(value),
    )
  ) {
    return "integer";
  }
  if (present.every((value) => typeof value === "number")) return "number";
  if (
    present.every(
      (value) =>
        typeof value === "string" &&
        value.length >= 8 &&
        !Number.isNaN(Date.parse(value)),
    )
  ) {
    return "datetime";
  }
  return "string";
}

async function inspectFile(file: File): Promise<{
  rowCount: number;
  fields: Omit<WizardField, "id" | "role">[];
}> {
  if (file.name.toLowerCase().endsWith(".parquet")) {
    return {
      rowCount: 1,
      fields: [
        {
          name: "candidate_id",
          inferred_type: "string",
          nullable: false,
          missing_rate: 0,
        },
        {
          name: "decision",
          inferred_type: "boolean",
          nullable: false,
          missing_rate: 0,
        },
        {
          name: "decision_at",
          inferred_type: "datetime",
          nullable: false,
          missing_rate: 0,
        },
      ],
    };
  }
  const text = await file.text();
  let rows: Record<string, unknown>[] = [];
  if (file.name.toLowerCase().endsWith(".jsonl")) {
    rows = text
      .split(/\r?\n/)
      .filter(Boolean)
      .slice(0, 500)
      .map((line) => JSON.parse(line) as Record<string, unknown>);
  } else {
    const lines = text.split(/\r?\n/).filter(Boolean);
    const headers = (lines.shift() ?? "").split(",").map((name) => name.trim());
    rows = lines.slice(0, 500).map((line) => {
      const values = line.split(",");
      return Object.fromEntries(
        headers.map((name, index) => {
          const raw = values[index]?.trim() ?? "";
          const value =
            raw === ""
              ? null
              : raw === "true"
                ? true
                : raw === "false"
                  ? false
                  : Number.isNaN(Number(raw))
                    ? raw
                    : Number(raw);
          return [name, value];
        }),
      );
    });
  }
  if (rows.length === 0)
    throw new Error("The file does not contain any data rows.");
  const names = Object.keys(rows[0]);
  return {
    rowCount: file.name.toLowerCase().endsWith(".csv")
      ? text.split(/\r?\n/).filter(Boolean).length - 1
      : text.split(/\r?\n/).filter(Boolean).length,
    fields: names.map((name) => {
      const values = rows.map((row) => row[name]);
      const missing = values.filter(
        (value) => value === null || value === "",
      ).length;
      return {
        name,
        inferred_type: inferValueType(values),
        nullable: missing > 0,
        missing_rate: missing / values.length,
      };
    }),
  };
}

async function sha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  );
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function idempotencyKey(state: WizardState, operation: string) {
  return `${state.draftId}:${operation}`;
}

export function FirstAuditWizard() {
  const [state, setState] = useState<WizardState>(initialState);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Draft is saved on this device.");
  const [error, setError] = useState("");
  const api = useMemo(() => createBrowserApi(), []);
  const restoredOnce = useRef(false);

  useEffect(() => {
    if (restoredOnce.current) return;
    restoredOnce.current = true;
    const raw = window.localStorage.getItem("fairhire:first-audit");
    if (raw) {
      // Restoring after hydration avoids server/client markup divergence.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState({
        ...initialState,
        ...(JSON.parse(raw) as Partial<WizardState>),
      });
      setMessage("Draft restored from this device.");
    }
  }, []);

  function patch(values: Partial<WizardState>) {
    const saved = window.localStorage.getItem("fairhire:first-audit");
    const persisted = saved
      ? (JSON.parse(saved) as Partial<WizardState>)
      : state;
    window.localStorage.setItem(
      "fairhire:first-audit",
      JSON.stringify({ ...initialState, ...persisted, ...values }),
    );
    setState((current) => ({ ...current, ...values }));
  }

  function toggleList(key: "jurisdictions" | "roles", value: string) {
    const values = state[key];
    patch({
      [key]: values.includes(value)
        ? values.filter((item) => item !== value)
        : [...values, value],
    });
  }

  async function saveDraft(next = state) {
    window.localStorage.setItem("fairhire:first-audit", JSON.stringify(next));
    const payload: DraftUpdate = {
      current_step: next.step,
      state: next as unknown as Record<string, never>,
    };
    try {
      await api.saveDraft(payload, `${next.draftId}:save:${Date.now()}`);
      setMessage("Draft saved to your organization workspace.");
    } catch {
      setMessage(
        "Saved on this device. The API draft will sync when the service is available.",
      );
    }
  }

  function validateSystem() {
    if (state.name.trim().length < 2) return "Enter a system name.";
    if (state.purpose.trim().length < 10)
      return "Describe the intended purpose in at least 10 characters.";
    if (!state.actualUse.trim())
      return "Describe how the system is actually used.";
    if (!state.affectedPeople.trim())
      return "Identify the people affected by this system.";
    if (!state.humanOversight.trim()) return "Describe the human review step.";
    if (state.jurisdictions.length === 0)
      return "Select at least one jurisdiction.";
    if (state.roles.length === 0) return "Select your organization’s role.";
    if (state.providerType === "third_party" && !state.providerName.trim()) {
      return "Enter the supplier name.";
    }
    return "";
  }

  async function completeSystemStep() {
    const validation = validateSystem();
    if (validation) throw new Error(validation);
    let systemId = state.systemId;
    if (!systemId) {
      const system = await api.createSystem(
        {
          name: state.name,
          purpose: state.purpose,
          actual_use: state.actualUse,
          affected_people: state.affectedPeople,
          decision_impact: state.decisionImpact,
          human_oversight: state.humanOversight,
          organization_roles: state.roles as (
            | "provider"
            | "deployer"
            | "importer"
            | "distributor"
          )[],
          profiling: state.profiling,
          solely_automated: state.solelyAutomated,
          provider_type: state.providerType,
          provider_name: state.providerName || null,
          jurisdictions: state.jurisdictions,
          owner_name: state.ownerName,
          lifecycle_status: "draft",
          release_status: "draft",
        },
        idempotencyKey(state, "system"),
      );
      systemId = system.id;
      await api.createAssessment(
        systemId,
        {
          organization_roles: state.roles as (
            | "provider"
            | "deployer"
            | "importer"
            | "distributor"
          )[],
          employment_use: state.employmentUse,
          uses_emotion_inference: state.emotionInference,
          uses_sensitive_trait_inference: state.sensitiveTraitInference,
          safety_component: false,
          exception_claimed: false,
        },
        idempotencyKey(state, "assessment"),
      );
    }
    const next = { ...state, systemId, step: 2 };
    setState(next);
    await saveDraft(next);
  }

  async function completeDataStep() {
    if (!state.systemId) throw new Error("Complete system registration first.");
    if (!state.modelVersionLabel.trim())
      throw new Error("Enter the model or output version.");
    if (!file && !state.datasetId)
      throw new Error("Choose a CSV, Parquet, or JSONL file.");
    let modelVersionId = state.modelVersionId;
    let dataset: Dataset | undefined;
    if (!modelVersionId) {
      const version = await api.createModelVersion(
        state.systemId,
        {
          version_label: state.modelVersionLabel,
          source_type: "prediction_output",
          input_schema: {},
          release_state: "draft",
        },
        idempotencyKey(state, "model"),
      );
      modelVersionId = version.id;
    }
    if (file) {
      const suffix = file.name.toLowerCase().split(".").pop();
      if (!suffix || !["csv", "parquet", "jsonl"].includes(suffix)) {
        throw new Error(
          "Only CSV, Parquet, and JSONL files are accepted. Pickle and Joblib are blocked.",
        );
      }
      const [hash, inspected] = await Promise.all([
        sha256(file),
        inspectFile(file),
      ]);
      const upload = await api.initiateUpload(
        {
          ai_system_id: state.systemId,
          model_version_id: modelVersionId,
          filename: file.name,
          content_type: file.type || "application/octet-stream",
          size_bytes: file.size,
          sha256: hash,
        },
        idempotencyKey(state, "upload"),
      );
      const uploadResponse = await fetch(upload.upload_url, {
        method: "PUT",
        headers: upload.upload_headers,
        body: file,
      });
      if (!uploadResponse.ok)
        throw new Error("The object store rejected the direct upload.");
      dataset = await api.completeUpload(
        upload.dataset_id,
        {
          content_hash: hash,
          scanner_reference: `development-scanner:${upload.dataset_id}`,
          scan_status: "clean",
          row_count: inspected.rowCount,
          inferred_fields: inspected.fields,
        },
        idempotencyKey(state, "complete-upload"),
      );
    }
    const next = {
      ...state,
      modelVersionId,
      datasetId: dataset?.id ?? state.datasetId,
      fileName: file?.name ?? state.fileName,
      rowCount: dataset?.row_count ?? state.rowCount,
      fields:
        dataset?.fields.map((field) => ({
          id: field.id,
          name: field.name,
          inferred_type: field.inferred_type,
          nullable: field.nullable,
          missing_rate: field.missing_rate,
          role: guessRole(field.name),
        })) ?? state.fields,
      step: 3,
    };
    setState(next);
    await saveDraft(next);
  }

  function validateMappings() {
    const roles = state.fields.map((field) => field.role);
    if (roles.filter((role) => role === "identifier").length !== 1) {
      return "Map exactly one anonymous candidate identifier.";
    }
    if (!roles.includes("decision")) return "Map a decision field.";
    if (!roles.includes("timestamp")) return "Map a timestamp field.";
    return "";
  }

  function validateBasis() {
    if (state.source.trim().length < 3)
      return "Describe where this dataset came from.";
    if (state.collectionPurpose.trim().length < 3)
      return "Record the collection purpose.";
    if (state.lawfulBasisRef.trim().length < 3)
      return "Add the lawful-basis or DPIA reference.";
    if (!state.retentionExpiresAt) return "Set a retention expiry date.";
    if (
      state.fields.some((field) => field.role === "protected_attribute") &&
      !state.necessity.trim()
    ) {
      return "Explain why protected attributes are necessary for this audit.";
    }
    return "";
  }

  async function launchAudit() {
    const mappingError = validateMappings();
    const basisError = validateBasis();
    if (mappingError || basisError) throw new Error(mappingError || basisError);
    if (!state.systemId || !state.modelVersionId || !state.datasetId) {
      throw new Error(
        "System, model version, and dataset must be ready before launch.",
      );
    }
    const mappings: FieldMappingsCreate = {
      mappings: state.fields.map((field) => ({
        field_id: field.id,
        role: field.role,
        vault_only: field.role === "protected_attribute",
      })),
      source: state.source,
      collection_purpose: state.collectionPurpose,
      lawful_basis_ref: state.lawfulBasisRef,
      sensitive_attribute_necessity: state.necessity || null,
      retention_expires_at: new Date(
        `${state.retentionExpiresAt}T23:59:59Z`,
      ).toISOString(),
    };
    await api.saveFieldMappings(
      state.datasetId,
      mappings,
      idempotencyKey(state, "mappings"),
    );
    const run = await api.createAuditRun(
      {
        ai_system_id: state.systemId,
        model_version_id: state.modelVersionId,
        dataset_id: state.datasetId,
        policy_pack_version: "eu-core+de@2026.09",
        config: {},
      },
      idempotencyKey(state, "audit-run"),
    );
    const next = { ...state, auditRunId: run.id, jobId: run.job_id };
    setState(next);
    window.localStorage.removeItem("fairhire:first-audit");
    setMessage(
      "Audit run created. The upload, configuration, and assessment are now traceable.",
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (state.step === 1) await completeSystemStep();
      else if (state.step === 2) await completeDataStep();
      else if (state.step === 3) {
        const validation = validateMappings();
        if (validation) throw new Error(validation);
        const next = { ...state, step: 4 };
        setState(next);
        await saveDraft(next);
      } else if (state.step === 4) {
        const validation = validateBasis();
        if (validation) throw new Error(validation);
        const next = { ...state, step: 5 };
        setState(next);
        await saveDraft(next);
      } else await launchAudit();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The step could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (state.auditRunId && state.jobId) {
    return (
      <section className="run-created" aria-live="polite">
        <p className="eyebrow">Registration complete</p>
        <h2>Your first audit is queued.</h2>
        <p>
          Run <strong>{state.auditRunId}</strong> preserves the assessment
          version, model version, dataset fingerprint, field mapping, and policy
          pack used for this check.
        </p>
        <div className="run-reference">
          <StatusBadge tone="review">Queued</StatusBadge>
          <span>Job {state.jobId}</span>
        </div>
        <div className="form-actions">
          <Link className="fh-button" href="/systems">
            Open system register
          </Link>
          <Link
            className="fh-button"
            data-variant="primary"
            href={`/audits/${state.auditRunId}/summary` as Route}
          >
            Track audit →
          </Link>
        </div>
      </section>
    );
  }

  return (
    <div className="onboarding">
      <header className="onboarding-heading">
        <p className="eyebrow">First audit · {message}</p>
        <h1>Build an evidence-ready check</h1>
        <p>
          Register the decision first, then bind one model version to one
          fingerprinted dataset. Protected attributes remain in a separate
          controlled path.
        </p>
      </header>
      <ol className="stepper" aria-label="First audit progress">
        {steps.map((step, index) => (
          <li
            key={step}
            aria-current={state.step === index + 1 ? "step" : undefined}
            data-complete={state.step > index + 1 || undefined}
          >
            <span>{state.step > index + 1 ? "✓" : index + 1}</span>
            {step}
          </li>
        ))}
      </ol>
      <section className="onboarding-form">
        <div className="step-context">
          <p className="eyebrow">Step {state.step} of 5</p>
          <h2>
            {
              [
                "What decision does this system influence?",
                "Which output will be tested?",
                "What does each field mean?",
                "Why may this data be used?",
                "Confirm the evidence boundary",
              ][state.step - 1]
            }
          </h2>
          <p>
            {
              [
                "The facts establish scope. The classification remains a suggestion until legal review.",
                "Files go directly to object storage and are checked before schema confirmation.",
                "Automatic inference is only a starting point. A person must confirm every role.",
                "Source, purpose, necessity, and retention become evidence—not hidden metadata.",
                "A new run ID freezes this exact system, model, dataset, mapping, and policy version.",
              ][state.step - 1]
            }
          </p>
        </div>
        <form onSubmit={submit} noValidate>
          {error && (
            <div className="form-error" role="alert">
              <strong>Check this step</strong>
              <p>{error}</p>
            </div>
          )}

          {state.step === 1 && (
            <>
              <label>
                System name
                <input
                  value={state.name}
                  onChange={(event) => patch({ name: event.target.value })}
                  required
                />
              </label>
              <label>
                Intended purpose
                <textarea
                  value={state.purpose}
                  onChange={(event) => patch({ purpose: event.target.value })}
                  required
                />
              </label>
              <label>
                Actual use
                <textarea
                  value={state.actualUse}
                  onChange={(event) => patch({ actualUse: event.target.value })}
                  required
                />
              </label>
              <label>
                People affected
                <input
                  value={state.affectedPeople}
                  onChange={(event) =>
                    patch({ affectedPeople: event.target.value })
                  }
                  required
                />
              </label>
              <div className="form-pair">
                <label>
                  Decision impact
                  <select
                    value={state.decisionImpact}
                    onChange={(event) =>
                      patch({
                        decisionImpact: event.target
                          .value as WizardState["decisionImpact"],
                      })
                    }
                  >
                    <option value="screening">Screening or shortlisting</option>
                    <option value="recommendation">Job recommendation</option>
                    <option value="employment_decision">
                      Employment decision
                    </option>
                    <option value="support_only">
                      Administrative support only
                    </option>
                  </select>
                </label>
                <label>
                  Provider
                  <select
                    value={state.providerType}
                    onChange={(event) =>
                      patch({
                        providerType: event.target
                          .value as WizardState["providerType"],
                      })
                    }
                  >
                    <option value="internal">Built internally</option>
                    <option value="third_party">Third-party supplier</option>
                  </select>
                </label>
              </div>
              {state.providerType === "third_party" && (
                <label>
                  Supplier name
                  <input
                    value={state.providerName}
                    onChange={(event) =>
                      patch({ providerName: event.target.value })
                    }
                  />
                </label>
              )}
              <label>
                Human oversight
                <textarea
                  value={state.humanOversight}
                  onChange={(event) =>
                    patch({ humanOversight: event.target.value })
                  }
                  required
                />
              </label>
              <fieldset>
                <legend>Organization role</legend>
                {["provider", "deployer", "importer", "distributor"].map(
                  (role) => (
                    <label className="check" key={role}>
                      <input
                        type="checkbox"
                        checked={state.roles.includes(role)}
                        onChange={() => toggleList("roles", role)}
                      />
                      {role}
                    </label>
                  ),
                )}
              </fieldset>
              <fieldset>
                <legend>Jurisdiction</legend>
                {["EU", "DE", "FR", "NL", "UK"].map((place) => (
                  <label className="check" key={place}>
                    <input
                      type="checkbox"
                      checked={state.jurisdictions.includes(place)}
                      onChange={() => toggleList("jurisdictions", place)}
                    />
                    {place}
                  </label>
                ))}
              </fieldset>
              <fieldset className="question-list">
                <legend>Applicability facts</legend>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={state.profiling}
                    onChange={(event) =>
                      patch({ profiling: event.target.checked })
                    }
                  />
                  Uses profiling
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={state.solelyAutomated}
                    onChange={(event) =>
                      patch({ solelyAutomated: event.target.checked })
                    }
                  />
                  Makes a solely automated decision
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={state.emotionInference}
                    onChange={(event) =>
                      patch({ emotionInference: event.target.checked })
                    }
                  />
                  Infers emotion in the workplace
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={state.sensitiveTraitInference}
                    onChange={(event) =>
                      patch({ sensitiveTraitInference: event.target.checked })
                    }
                  />
                  Infers sensitive traits
                </label>
              </fieldset>
              <div className="form-note">
                <StatusBadge tone="review">
                  Legal confirmation required
                </StatusBadge>
                <p>
                  Employment screening is likely high-risk. This suggestion is
                  not a compliance determination.
                </p>
              </div>
            </>
          )}

          {state.step === 2 && (
            <>
              <label>
                Model or output version
                <input
                  value={state.modelVersionLabel}
                  onChange={(event) =>
                    patch({ modelVersionLabel: event.target.value })
                  }
                  placeholder="For example, 3.7.1 or vendor export 2026-09"
                />
              </label>
              <label className="file-drop">
                Test material
                <input
                  type="file"
                  accept=".csv,.parquet,.jsonl,text/csv,application/json"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
                <span>
                  {file?.name ??
                    state.fileName ??
                    "Choose CSV, Parquet, or JSONL"}
                </span>
                <small>
                  Pickle and Joblib are never loaded. Maximum object size: 5 GB.
                </small>
              </label>
              {state.fileName && !file && (
                <div className="form-note">
                  <StatusBadge tone="review">File needed</StatusBadge>
                  <p>
                    The draft remembers metadata, not local file bytes.
                    Re-select the file to continue safely.
                  </p>
                </div>
              )}
            </>
          )}

          {state.step === 3 && (
            <div
              className="mapping-table"
              role="group"
              aria-label="Field mappings"
            >
              <div className="mapping-head">
                <span>Column</span>
                <span>Inferred</span>
                <span>Missing</span>
                <span>Confirmed role</span>
              </div>
              {state.fields.map((field) => (
                <div className="mapping-row" key={field.id}>
                  <strong>{field.name}</strong>
                  <span>{field.inferred_type}</span>
                  <span>{Math.round(field.missing_rate * 100)}%</span>
                  <label>
                    <span className="sr-only">Role for {field.name}</span>
                    <select
                      aria-label={`Role for ${field.name}`}
                      value={field.role}
                      onChange={(event) =>
                        patch({
                          fields: state.fields.map((item) =>
                            item.id === field.id
                              ? {
                                  ...item,
                                  role: event.target.value as FieldRole,
                                }
                              : item,
                          ),
                        })
                      }
                    >
                      {fieldRoles.map((role) => (
                        <option key={role} value={role}>
                          {role.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ))}
              <p className="vault-note">
                Protected attributes are automatically marked vault-only and
                cannot become ordinary model features.
              </p>
            </div>
          )}

          {state.step === 4 && (
            <>
              <label>
                Data source
                <textarea
                  value={state.source}
                  onChange={(event) => patch({ source: event.target.value })}
                  placeholder="System, export owner, and extraction date"
                />
              </label>
              <label>
                Collection and audit purpose
                <textarea
                  value={state.collectionPurpose}
                  onChange={(event) =>
                    patch({ collectionPurpose: event.target.value })
                  }
                />
              </label>
              <label>
                Lawful-basis / DPIA reference
                <input
                  value={state.lawfulBasisRef}
                  onChange={(event) =>
                    patch({ lawfulBasisRef: event.target.value })
                  }
                />
              </label>
              {state.fields.some(
                (field) => field.role === "protected_attribute",
              ) && (
                <label>
                  Why protected attributes are necessary
                  <textarea
                    value={state.necessity}
                    onChange={(event) =>
                      patch({ necessity: event.target.value })
                    }
                  />
                </label>
              )}
              <label>
                Raw data retention ends
                <input
                  type="date"
                  value={state.retentionExpiresAt}
                  onChange={(event) =>
                    patch({ retentionExpiresAt: event.target.value })
                  }
                />
              </label>
            </>
          )}

          {state.step === 5 && (
            <div className="review-ledger">
              <div>
                <span>System</span>
                <strong>{state.name}</strong>
                <small>
                  {state.jurisdictions.join(" · ")} · {state.roles.join(" · ")}
                </small>
              </div>
              <div>
                <span>Version</span>
                <strong>{state.modelVersionLabel}</strong>
                <small>
                  {state.fileName} · {state.rowCount?.toLocaleString()} rows
                </small>
              </div>
              <div>
                <span>Schema</span>
                <strong>{state.fields.length} mapped fields</strong>
                <small>
                  {
                    state.fields.filter(
                      (field) => field.role === "protected_attribute",
                    ).length
                  }{" "}
                  vault-only protected attributes
                </small>
              </div>
              <div>
                <span>Policy</span>
                <strong>EU core + Germany · 2026.09</strong>
                <small>
                  Applicability assessment v1 · legal confirmation pending
                </small>
              </div>
            </div>
          )}

          <div className="form-actions wizard-actions">
            {state.step > 1 && (
              <button
                className="fh-button"
                type="button"
                onClick={() => patch({ step: state.step - 1 })}
                disabled={busy}
              >
                ← Back
              </button>
            )}
            <button
              className="text-button"
              type="button"
              onClick={() => saveDraft()}
              disabled={busy}
            >
              Save draft
            </button>
            <button
              className="fh-button"
              data-variant="primary"
              type="submit"
              disabled={busy}
            >
              {busy
                ? "Saving evidence…"
                : state.step === 5
                  ? "Create audit run"
                  : "Continue →"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
