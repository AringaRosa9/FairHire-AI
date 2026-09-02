import type { ReactNode } from "react";
import type { StatusTone } from "./types";

type Props = { children: ReactNode; tone: StatusTone };

export function StatusBadge({ children, tone }: Props) {
  return (
    <span className="fh-status" data-tone={tone}>
      {children}
    </span>
  );
}
