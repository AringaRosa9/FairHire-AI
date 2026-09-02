# Desktop and mobile acceptance specification

## Context

Desktop users perform focused evidence review with keyboard and pointer. Tablet users may review approvals with touch. Mobile is primarily a decision triage surface, but it must not remove blocking status, owner, due date or approval actions.

| Width/context | Navigation | Content adaptation | Acceptance |
|---|---|---|---|
| 1120px+ desk | Persistent 248px navigation | Multi-column portfolio, full registry columns | No content stretches beyond 1440px; all actions keyboard reachable |
| 801–1119px desk/tablet | 86px icon rail | Decision rail moves under registry; dense tables preserved | Navigation labels have accessible names; touch targets remain 44px |
| 320–800px phone/tablet | Drawer opened from sticky header | Single-column flow; system rows become labeled evidence blocks | Status, owner, scope and row action remain visible; search stays present |
| coarse pointer | Same information architecture | Controls increase to 48px minimum | No hover-only interaction |
| reduced motion | Same layout | Drawer and skip-link transitions disabled | No required information conveyed by motion |
| print | Navigation/actions removed | Evidence content expands in one column | Dark text on white; logical rules retained |

QA baselines: 320×568, 390×844, 768×1024 portrait, 1024×768 landscape, 1440×900 and 2560×1440. Playwright covers desktop Chromium and mobile Safari emulation; real-device checks remain required before pilot release.

