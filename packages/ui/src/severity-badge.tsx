import type { Severity } from "./types";

const labels: Record<Severity, string> = {
  critical: "Crit",
  high: "High",
  medium: "Med",
  low: "Low",
};

export function SeverityBadge({ level }: { level: Severity }) {
  return (
    <span
      className="fh-severity"
      data-level={level}
      aria-label={`${level} severity`}
    >
      {labels[level]}
    </span>
  );
}
