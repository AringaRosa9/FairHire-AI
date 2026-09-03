"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { createBrowserApi } from "@/lib/browser-api";
import { Icon } from "./icons";

const mainLinks = [
  { href: "/portfolio", label: "Overview", icon: "portfolio" as const },
  { href: "/systems", label: "Systems", icon: "systems" as const, count: true },
  { href: "/audits/new", label: "New audit", icon: "checks" as const },
  {
    href: "/findings",
    label: "Action items",
    icon: "findings" as const,
    count: "8",
  },
  { href: "/approvals", label: "Approvals", icon: "checks" as const },
  { href: "/tasks", label: "Due tasks", icon: "findings" as const },
  { href: "/reports", label: "Reports", icon: "reports" as const },
] as const;

const pageMeta: Record<string, { eyebrow: string; context: string }> = {
  "/portfolio": {
    eyebrow: "Governance portfolio",
    context: "Recruitment AI systems · EU operations",
  },
  "/systems": {
    eyebrow: "System registry",
    context: "Purpose, ownership and release posture",
  },
  "/onboarding": {
    eyebrow: "Getting started",
    context: "First audit · saved as a draft",
  },
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [identity, setIdentity] = useState({
    organization: "Northstar Hiring Group",
    region: "EU workspace",
    displayName: "Maya Chen",
    role: "Admin",
    initials: "MC",
    systemCount: "4",
  });
  const api = useMemo(() => createBrowserApi(), []);
  useEffect(() => {
    void Promise.all([api.session(), api.listSystems()])
      .then(([session, systems]) => {
        const initials = session.display_name
          .split(" ")
          .map((part) => part[0])
          .join("")
          .slice(0, 2)
          .toUpperCase();
        setIdentity({
          organization: session.organization_name,
          region: "EU workspace",
          displayName: session.display_name,
          role: session.role.replaceAll("_", " "),
          initials,
          systemCount: String(systems.total),
        });
      })
      .catch(() => undefined);
  }, [api]);
  const meta = pageMeta[pathname] ?? {
    eyebrow: "Assurance workspace",
    context: "Evidence, controls and accountable decisions",
  };

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <aside
        className={`sidebar ${open ? "is-open" : ""}`}
        aria-label="Primary navigation"
      >
        <div className="sidebar-head">
          <Link className="brand" href="/portfolio">
            <span className="brand-mark" aria-hidden="true">
              Fh
            </span>
            <span>
              <strong>FairHire AI</strong>
              <small>Assurance workspace</small>
            </span>
          </Link>
          <button
            className="icon-button close-menu"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <Icon name="close" />
          </button>
        </div>
        <p className="nav-label">Main tools</p>
        <nav>
          <ul className="nav-list">
            {mainLinks.map((link) => {
              const active =
                pathname === link.href ||
                (link.href !== "/portfolio" &&
                  pathname.startsWith(`${link.href}/`));
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    onNavigate={() => setOpen(false)}
                    className={active ? "nav-link active" : "nav-link"}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon name={link.icon} />
                    <span>{link.label}</span>
                    {"count" in link && (
                      <em>
                        {link.href === "/systems"
                          ? identity.systemCount
                          : link.count}
                      </em>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="sidebar-foot">
          <p>{identity.organization}</p>
          <span>
            {identity.region} · {identity.role}
          </span>
          <Link href="/login">{identity.displayName} · Sign out</Link>
        </div>
      </aside>
      {open && (
        <button
          className="scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button menu-button"
            onClick={() => setOpen(true)}
            aria-label="Open navigation"
          >
            <Icon name="menu" />
          </button>
          <div className="topbar-context">
            <p>{meta.eyebrow}</p>
            <strong>{meta.context}</strong>
          </div>
          <div className="topbar-actions">
            <span className="environment">EU region</span>
            <span
              className="avatar"
              aria-label={`Signed in as ${identity.displayName}`}
            >
              {identity.initials}
            </span>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
