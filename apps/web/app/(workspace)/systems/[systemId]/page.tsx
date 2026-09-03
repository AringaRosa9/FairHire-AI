import { notFound } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@fairhire/ui";
import { getSystemDetail } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SystemDetailPage({
  params,
}: {
  params: Promise<{ systemId: string }>;
}) {
  const { systemId } = await params;
  const { system, assessments, modelVersions, source } =
    await getSystemDetail(systemId);
  if (!system) notFound();
  const blocked = system.release_status === "blocked";
  return (
    <>
      <Link className="back-link" href="/systems">
        ← Back to systems
      </Link>
      <header className="detail-header">
        <div>
          <p className="eyebrow">
            AI system · Assessment v{system.assessment_version}
          </p>
          <h1>{system.name}</h1>
          <p>
            {system.purpose} across {system.jurisdictions.join(", ")}. Owned by{" "}
            {system.owner_name}.
          </p>
        </div>
        <StatusBadge
          tone={
            blocked
              ? "blocked"
              : system.release_status === "approved"
                ? "approved"
                : "review"
          }
        >
          {blocked
            ? "Do not use"
            : system.release_status === "approved"
              ? "Can be used"
              : "Needs confirmation"}
        </StatusBadge>
      </header>
      <section className="detail-ledger">
        <h2>Decision record</h2>
        <dl>
          <div>
            <dt>Intended purpose</dt>
            <dd>{system.purpose}</dd>
          </div>
          <div>
            <dt>Provider</dt>
            <dd>{system.provider_name ?? "Internal model"}</dd>
          </div>
          <div>
            <dt>Jurisdictions</dt>
            <dd>{system.jurisdictions.join(", ")}</dd>
          </div>
          <div>
            <dt>Next review</dt>
            <dd>
              {system.next_review_at
                ? new Date(system.next_review_at).toLocaleDateString("en-GB", {
                    dateStyle: "long",
                  })
                : "Not scheduled"}
            </dd>
          </div>
          <div>
            <dt>Legal classification</dt>
            <dd>
              {assessments[0]
                ? `${assessments[0].risk_class.replaceAll("_", " ")} · legal confirmation required`
                : "Assessment not yet completed"}
            </dd>
          </div>
        </dl>
      </section>
      <div className="detail-columns">
        <section className="version-list" aria-labelledby="assessment-history">
          <p className="eyebrow">Rule evidence</p>
          <h2 id="assessment-history">Applicability history</h2>
          {assessments.length ? (
            assessments.map((assessment) => (
              <article key={assessment.id}>
                <strong>Assessment v{assessment.version}</strong>
                <span>
                  {assessment.risk_class.replaceAll("_", " ")} ·{" "}
                  {assessment.rule_pack_version}
                </span>
                <small>{assessment.rationale}</small>
              </article>
            ))
          ) : (
            <p className="quiet-empty">
              No versioned assessment is available{" "}
              {source === "fixture" ? "while the API is offline" : "yet"}.
            </p>
          )}
        </section>
        <section className="version-list" aria-labelledby="model-history">
          <p className="eyebrow">Bound artifacts</p>
          <h2 id="model-history">Model and output versions</h2>
          {modelVersions.length ? (
            modelVersions.map((version) => (
              <article key={version.id}>
                <strong>{version.version_label}</strong>
                <span>
                  {version.source_type.replaceAll("_", " ")} ·{" "}
                  {version.release_state}
                </span>
                <small>
                  {version.content_hash
                    ? `SHA-256 ${version.content_hash.slice(0, 14)}…`
                    : "Hash captured when material is uploaded"}
                </small>
              </article>
            ))
          ) : (
            <p className="quiet-empty">
              No model or output version has been registered.
            </p>
          )}
        </section>
      </div>
    </>
  );
}
