import { PageIntro } from "@/components/page-intro";
import { StatusBadge } from "@fairhire/ui";

export default function ReportsPage() {
  return (
    <>
      <PageIntro
        eyebrow="109 required items · 74 complete"
        title="Reports traceable to their source"
        lead="Every report records the model version, data fingerprint, method, changes and approver so an independent reviewer can reproduce it."
      />
      <section className="report-list">
        <article>
          <div>
            <p className="eyebrow">Risk assessment · v3</p>
            <h2>TalentRank EU release review</h2>
            <span>Audit AR-2841 · Model 3.7.1 · 184,290 rows</span>
          </div>
          <StatusBadge tone="review">Approval waiting</StatusBadge>
          <button className="fh-button">Review gaps</button>
        </article>
        <article>
          <div>
            <p className="eyebrow">System card · v2</p>
            <h2>CV Lens supplier evidence</h2>
            <span>Content hash 31e0…b7a4 · approved 15 Aug</span>
          </div>
          <StatusBadge tone="approved">Approved</StatusBadge>
          <button className="fh-button">Download</button>
        </article>
      </section>
    </>
  );
}
