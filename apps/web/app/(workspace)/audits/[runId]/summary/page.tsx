import { AuditRunStatus } from "@/components/audit-run-status";

export default async function AuditRunSummaryPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  return <AuditRunStatus runId={runId} />;
}
