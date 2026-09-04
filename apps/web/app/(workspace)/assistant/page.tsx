import { ComplianceAssistant } from "@/components/compliance-assistant";
import { PageIntro } from "@/components/page-intro";
import { getAssistantWorkspace, getSystems } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AssistantPage() {
  const [workspace, systems] = await Promise.all([
    getAssistantWorkspace(),
    getSystems(),
  ]);
  return (
    <>
      <PageIntro
        eyebrow={`${workspace.sources.length} governed sources · ${workspace.answers.length} recorded answers`}
        title="Compliance help that shows its work"
        lead="Ask about the current system, policy or evidence package. Every substantive paragraph points to an authorized source, carries its rule date and says whether it is fact, inference or recommendation."
      />
      <ComplianceAssistant
        systems={systems.items}
        sources={workspace.sources}
        initialAnswers={workspace.answers}
        offline={workspace.source === "fixture" || systems.source === "fixture"}
      />
    </>
  );
}
