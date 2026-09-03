"use client";

import type { AuditRun, BackgroundJob } from "@fairhire/api-client";
import { StatusBadge } from "@fairhire/ui";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createBrowserApi } from "@/lib/browser-api";

const tones = {
  queued: "review",
  running: "review",
  succeeded: "approved",
  failed: "blocked",
  cancelling: "review",
  cancelled: "draft",
} as const;

export function AuditRunStatus({ runId }: { runId: string }) {
  const api = useMemo(() => createBrowserApi(), []);
  const [run, setRun] = useState<AuditRun | null>(null);
  const [job, setJob] = useState<BackgroundJob | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const nextRun = await api.getAuditRun(runId);
      const nextJob = await api.getJob(nextRun.job_id);
      setRun(nextRun);
      setJob(nextJob);
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Run status is unavailable.",
      );
    }
  }, [api, runId]);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [refresh]);

  return (
    <>
      <Link className="back-link" href="/portfolio">
        ← Back to portfolio
      </Link>
      <header className="detail-header run-header">
        <div>
          <p className="eyebrow">Audit run · immutable input boundary</p>
          <h1>{run ? `Run ${run.id.slice(0, 18)}…` : "Loading audit run"}</h1>
          <p>
            The status refreshes every three seconds. A failure preserves its
            error and attempt count; cancelling never deletes evidence.
          </p>
        </div>
        {run && (
          <StatusBadge tone={tones[run.status]}>
            {run.status.replaceAll("_", " ")}
          </StatusBadge>
        )}
      </header>
      {error && (
        <div className="form-error" role="alert">
          <strong>Status unavailable</strong>
          <p>{error}</p>
        </div>
      )}
      {run && job && (
        <section className="run-status-grid" aria-label="Audit run status">
          <div>
            <span>System</span>
            <strong>{run.ai_system_id}</strong>
          </div>
          <div>
            <span>Model version</span>
            <strong>{run.model_version_id}</strong>
          </div>
          <div>
            <span>Dataset</span>
            <strong>{run.dataset_id}</strong>
          </div>
          <div>
            <span>Policy pack</span>
            <strong>{run.policy_pack_version}</strong>
          </div>
          <div>
            <span>Data fingerprint</span>
            <strong className="hash-value">{run.data_fingerprint}</strong>
          </div>
          <div>
            <span>Queue attempt</span>
            <strong>
              {job.attempt} of {job.max_attempts}
            </strong>
          </div>
          <div>
            <span>Progress</span>
            <strong>{job.progress}%</strong>
          </div>
          <div>
            <span>Submitted by</span>
            <strong>{run.submitted_by}</strong>
          </div>
        </section>
      )}
    </>
  );
}
