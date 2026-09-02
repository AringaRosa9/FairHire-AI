import { notFound } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@fairhire/ui";
import { getSystems } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SystemDetailPage({
  params,
}: {
  params: Promise<{ systemId: string }>;
}) {
  const { systemId } = await params;
  const { items } = await getSystems();
  const system = items.find((item) => item.id === systemId);
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
            <dd>Employment high-risk use · legal confirmation required</dd>
          </div>
        </dl>
      </section>
    </>
  );
}
