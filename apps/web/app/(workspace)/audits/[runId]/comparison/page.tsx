import { AuditWorkbench } from "@/components/audit-workbench";

export default async function AuditComparisonPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  return <AuditWorkbench runId={runId} view="comparison" />;
}
