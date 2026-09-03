import type { Metadata } from "next";
import { FirstAuditWizard } from "@/components/first-audit-wizard";

export const metadata: Metadata = { title: "First audit" };

export default function OnboardingPage() {
  return <FirstAuditWizard />;
}
