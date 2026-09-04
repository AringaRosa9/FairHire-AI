"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { createBrowserApi } from "@/lib/browser-api";
import { Icon } from "./icons";

const mainLinks = [
  { href: "/portfolio", label: "overview", icon: "portfolio" as const },
  { href: "/systems", label: "systems", icon: "systems" as const, count: true },
  { href: "/audits/new", label: "newAudit", icon: "checks" as const },
  {
    href: "/findings",
    label: "actionItems",
    icon: "findings" as const,
    count: "8",
  },
  { href: "/approvals", label: "approvals", icon: "checks" as const },
  { href: "/tasks", label: "dueTasks", icon: "findings" as const },
  { href: "/reports", label: "reports", icon: "reports" as const },
  { href: "/assistant", label: "complianceHelp", icon: "checks" as const },
] as const;

type Locale = "en" | "zh-CN";
type MessageKey =
  | (typeof mainLinks)[number]["label"]
  | "assuranceWorkspace"
  | "closeNavigation"
  | "euRegion"
  | "euWorkspace"
  | "mainTools"
  | "openNavigation"
  | "primaryNavigation"
  | "signOut"
  | "signedInAs"
  | "skipToContent"
  | "switchLanguage";

const messages: Record<Locale, Record<MessageKey, string>> = {
  en: {
    overview: "Overview",
    systems: "Systems",
    newAudit: "New audit",
    actionItems: "Action items",
    approvals: "Approvals",
    dueTasks: "Due tasks",
    reports: "Reports",
    complianceHelp: "Compliance help",
    assuranceWorkspace: "Assurance workspace",
    closeNavigation: "Close navigation",
    euRegion: "EU region",
    euWorkspace: "EU workspace",
    mainTools: "Main tools",
    openNavigation: "Open navigation",
    primaryNavigation: "Primary navigation",
    signOut: "Sign out",
    signedInAs: "Signed in as",
    skipToContent: "Skip to content",
    switchLanguage: "Switch to Chinese",
  },
  "zh-CN": {
    overview: "概览",
    systems: "系统登记",
    newAudit: "新建审计",
    actionItems: "整改事项",
    approvals: "审批",
    dueTasks: "到期任务",
    reports: "报告",
    complianceHelp: "合规帮助",
    assuranceWorkspace: "保障工作区",
    closeNavigation: "关闭导航",
    euRegion: "欧盟区域",
    euWorkspace: "欧盟工作区",
    mainTools: "主要工具",
    openNavigation: "打开导航",
    primaryNavigation: "主导航",
    signOut: "退出登录",
    signedInAs: "当前用户",
    skipToContent: "跳到主要内容",
    switchLanguage: "切换为英文",
  },
};

const pageMeta: Record<
  string,
  Record<Locale, { eyebrow: string; context: string }>
> = {
  "/portfolio": {
    en: {
      eyebrow: "Governance portfolio",
      context: "Recruitment AI systems · EU operations",
    },
    "zh-CN": { eyebrow: "治理组合", context: "招聘 AI 系统 · 欧盟运营" },
  },
  "/systems": {
    en: {
      eyebrow: "System registry",
      context: "Purpose, ownership and release posture",
    },
    "zh-CN": { eyebrow: "系统登记", context: "用途、责任人与发布状态" },
  },
  "/onboarding": {
    en: {
      eyebrow: "Getting started",
      context: "First audit · saved as a draft",
    },
    "zh-CN": { eyebrow: "开始使用", context: "首次审计 · 自动保存草稿" },
  },
  "/reports": {
    en: {
      eyebrow: "Evidence & reports",
      context: "Versioned, traceable and exportable",
    },
    "zh-CN": { eyebrow: "证据与报告", context: "版本化、可追溯、可导出" },
  },
  "/assistant": {
    en: {
      eyebrow: "Read-only assistant",
      context: "Cited policy and project evidence",
    },
    "zh-CN": { eyebrow: "只读助手", context: "带引用的政策与项目证据" },
  },
};

function subscribeLocale(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("fairhire-locale-change", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("fairhire-locale-change", callback);
  };
}

function browserLocale(): Locale {
  return window.localStorage.getItem("fairhire-locale") === "zh-CN"
    ? "zh-CN"
    : "en";
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const locale = useSyncExternalStore<Locale>(
    subscribeLocale,
    browserLocale,
    (): Locale => "en",
  );
  const [identity, setIdentity] = useState({
    organization: "Northstar Hiring Group",
    region: "EU workspace",
    displayName: "Maya Chen",
    role: "Admin",
    initials: "MC",
    systemCount: "4",
  });
  const api = useMemo(() => createBrowserApi(), []);
  const t = (key: MessageKey) => messages[locale][key];
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
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
  const meta =
    pageMeta[pathname]?.[locale] ??
    (locale === "zh-CN"
      ? { eyebrow: "保障工作区", context: "证据、控制与责任明确的决策" }
      : {
          eyebrow: "Assurance workspace",
          context: "Evidence, controls and accountable decisions",
        });

  const toggleLocale = () => {
    const nextLocale: Locale = locale === "en" ? "zh-CN" : "en";
    window.localStorage.setItem("fairhire-locale", nextLocale);
    window.dispatchEvent(new Event("fairhire-locale-change"));
  };

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        {t("skipToContent")}
      </a>
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <div className="sidebar-head">
          <Link className="brand" href="/portfolio">
            <span className="brand-mark" aria-hidden="true">
              Fh
            </span>
            <span>
              <strong>FairHire AI</strong>
              <small>{t("assuranceWorkspace")}</small>
            </span>
          </Link>
          <button
            className="icon-button close-menu"
            onClick={() => setOpen(false)}
            aria-label={t("closeNavigation")}
          >
            <Icon name="close" />
          </button>
        </div>
        <p className="nav-label">{t("mainTools")}</p>
        <nav aria-label={t("primaryNavigation")}>
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
                    <span>{t(link.label)}</span>
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
            {t("euWorkspace")} · {identity.role}
          </span>
          <Link href="/login">
            {identity.displayName} · {t("signOut")}
          </Link>
        </div>
      </aside>
      {open && (
        <button
          className="scrim"
          aria-label={t("closeNavigation")}
          onClick={() => setOpen(false)}
        />
      )}
      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button menu-button"
            onClick={() => setOpen(true)}
            aria-label={t("openNavigation")}
          >
            <Icon name="menu" />
          </button>
          <div className="topbar-context">
            <p>{meta.eyebrow}</p>
            <strong>{meta.context}</strong>
          </div>
          <div className="topbar-actions">
            <button
              className="locale-switch"
              type="button"
              onClick={toggleLocale}
              aria-label={t("switchLanguage")}
            >
              {locale === "en" ? "中" : "EN"}
            </button>
            <span className="environment">{t("euRegion")}</span>
            <span
              className="avatar"
              aria-label={`${t("signedInAs")} ${identity.displayName}`}
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
