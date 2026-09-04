import { PageIntro } from "@/components/page-intro";
import { ReportCenter } from "@/components/report-center";
import { getReports, getSystems } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ReportsPage() {
  const [reports, systems] = await Promise.all([getReports(), getSystems()]);
  const approved = reports.items.filter(
    (item) => item.status === "approved",
  ).length;
  const gaps = reports.items.reduce(
    (total, item) => total + item.evidence_gaps.length,
    0,
  );
  return (
    <>
      <PageIntro
        eyebrow={`${reports.items.length} versions · ${approved} approved · ${gaps} open gaps`}
        title="Reports traceable to their source"
        lead="Every report records the model version, data fingerprint, method, changes and approver so an independent reviewer can reproduce it."
      />
      <ReportCenter
        initialReports={reports.items}
        systems={systems.items}
        offline={reports.source === "fixture" || systems.source === "fixture"}
      />
    </>
  );
}
