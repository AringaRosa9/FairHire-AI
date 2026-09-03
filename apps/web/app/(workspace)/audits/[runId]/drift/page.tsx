import { AuditWorkbench } from "@/components/audit-workbench";

export default async function AuditDriftPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  return <AuditWorkbench runId={runId} view="drift" />;
}
