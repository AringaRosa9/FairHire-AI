import type { Metadata } from "next";
import Link from "next/link";
import { PageIntro } from "@/components/page-intro";
import { SystemRegistry } from "@/components/system-registry";
import { getSystems } from "@/lib/api";

export const metadata: Metadata = { title: "Systems" };
export const dynamic = "force-dynamic";

export default async function SystemsPage() {
  const { items, source } = await getSystems();
  return (
    <>
      <PageIntro
        eyebrow={`${items.length} systems · 2 from outside suppliers`}
        title="Recruitment AI systems"
        lead="See what each system does, who provides it, where it is used, and whether the current evidence supports use."
        action={
          <Link href="/onboarding" className="fh-button" data-variant="primary">
            Register a system
          </Link>
        }
      />
      <p className="data-provenance">
        {source === "api"
          ? "Organization-scoped API data"
          : "Typed review fixture · start the API for live organization data"}
      </p>
      <SystemRegistry systems={items} />
    </>
  );
}
