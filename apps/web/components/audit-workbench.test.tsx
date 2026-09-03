import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuditWorkbench } from "./audit-workbench";

afterEach(() => vi.unstubAllGlobals());

describe("AuditWorkbench", () => {
  it("keeps uncertainty, evidence state, and policy trace together", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/audit-runs/run-1")) {
          return Response.json({
            id: "run-1",
            organization_id: "org-northstar",
            ai_system_id: "sys-1",
            model_version_id: "model-1",
            dataset_id: "dataset-1",
            config_version: 1,
            policy_pack_version: "eu-core+de@2026.09",
            config_snapshot: { random_seed: 42 },
            data_fingerprint: "f".repeat(64),
            status: "succeeded",
            job_id: "job-1",
            error_code: null,
            error_detail: null,
            submitted_by: "maya",
            submitted_at: "2026-09-03T00:00:00Z",
            started_at: "2026-09-03T00:00:01Z",
            completed_at: "2026-09-03T00:00:03Z",
          });
        }
        if (url.endsWith("/jobs/job-1")) {
          return Response.json({
            id: "job-1",
            organization_id: "org-northstar",
            task_name: "audit.analyze",
            resource_type: "audit_run",
            resource_id: "run-1",
            status: "succeeded",
            attempt: 1,
            max_attempts: 3,
            progress: 100,
            error_code: null,
            error_detail: null,
            cancellation_requested: false,
            submitted_at: "2026-09-03T00:00:00Z",
            updated_at: "2026-09-03T00:00:03Z",
          });
        }
        return Response.json({
          audit_run_id: "run-1",
          calculation_version: "fairhire-binary-audit@1.0.0",
          status_counts: { review_required: 1 },
          evidence_gaps: [],
          items: [
            {
              id: "metric-1",
              audit_run_id: "run-1",
              category: "fairness",
              metric_key: "demographic_parity_ratio",
              protected_attribute: "gender",
              reference_group: "women",
              comparison_group: "men",
              value: 0.78,
              lower_bound: 0.69,
              upper_bound: 0.88,
              status: "review_required",
              threshold: 0.8,
              threshold_operator: ">=",
              threshold_source: { source_id: "strategy-eu-binary-v1" },
              raw_counts: { comparison: { n: 250, selected: 98 } },
              method: "stratified_bootstrap_percentile",
              calculation_version: "fairhire-binary-audit@1.0.0",
              details: { random_seed: 42 },
              created_at: "2026-09-03T00:00:03Z",
            },
          ],
        });
      }),
    );

    render(<AuditWorkbench runId="run-1" view="fairness" />);
    expect(
      await screen.findByText("Demographic parity ratio"),
    ).toBeInTheDocument();
    expect(screen.getByText("0.69–0.88")).toBeInTheDocument();
    expect(screen.getByText("review required")).toBeInTheDocument();
    expect(screen.getByText("Counts & policy")).toBeInTheDocument();
  });
});
