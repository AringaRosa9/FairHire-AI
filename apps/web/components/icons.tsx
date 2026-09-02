import type { SVGProps } from "react";

export function Icon({
  name,
  ...props
}: SVGProps<SVGSVGElement> & {
  name:
    | "portfolio"
    | "systems"
    | "checks"
    | "findings"
    | "reports"
    | "menu"
    | "close";
}) {
  const paths = {
    portfolio: (
      <>
        <path d="M4 19V9m8 10V5m8 14v-7" />
        <path d="M2.5 19.5h19" />
      </>
    ),
    systems: (
      <>
        <rect x="4" y="4" width="16" height="16" rx="2" />
        <path d="M8 9h8M8 13h5M8 17h7" />
      </>
    ),
    checks: (
      <>
        <path d="M5 4h14v16H5z" />
        <path d="m8 9 2 2 5-5M8 15h8" />
      </>
    ),
    findings: (
      <>
        <path d="m12 3 9 17H3L12 3Z" />
        <path d="M12 9v5m0 3h.01" />
      </>
    ),
    reports: (
      <>
        <path d="M6 3h9l3 3v15H6z" />
        <path d="M15 3v4h4M9 12h6M9 16h6" />
      </>
    ),
    menu: <path d="M4 7h16M4 12h16M4 17h16" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
  };
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
