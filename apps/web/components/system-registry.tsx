"use client";

import type { AISystem } from "@fairhire/api-client";
import { StatusBadge } from "@fairhire/ui";
import Link from "next/link";
import { useMemo, useState } from "react";

const status = {
  approved: { tone: "approved" as const, label: "Can be used" },
  review_required: { tone: "review" as const, label: "Needs confirmation" },
  blocked: { tone: "blocked" as const, label: "Do not use" },
  draft: { tone: "draft" as const, label: "Draft" },
  insufficient_evidence: {
    tone: "insufficient" as const,
    label: "Insufficient evidence",
  },
};

export function SystemRegistry({ systems }: { systems: AISystem[] }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () =>
      systems.filter((system) =>
        [
          system.name,
          system.owner_name,
          status[system.release_status].label,
          system.provider_name ?? "internal",
        ]
          .join(" ")
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [query, systems],
  );
  return (
    <section className="registry" aria-labelledby="registry-heading">
      <div className="registry-tools">
        <div>
          <h2 id="registry-heading">System register</h2>
          <p>
            {filtered.length} of {systems.length} systems shown
          </p>
        </div>
        <label>
          <span>Filter systems</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            type="search"
            placeholder="Name, owner, supplier, or status"
          />
        </label>
      </div>
      <div className="registry-header" aria-hidden="true">
        <span>System</span>
        <span>Provider</span>
        <span>Scope</span>
        <span>Release posture</span>
        <span />
      </div>
      <div className="registry-list">
        {filtered.map((system, index) => (
          <article className="registry-row" key={system.id}>
            <div className="system-name">
              <span className="system-index">0{index + 1}</span>
              <div>
                <strong>{system.name}</strong>
                <small>
                  {system.purpose} · {system.lifecycle_status}
                </small>
              </div>
            </div>
            <div data-label="Provider">
              <strong>
                {system.provider_type === "internal"
                  ? "Built and used by us"
                  : "Bought from a supplier"}
              </strong>
              <small>{system.provider_name ?? "Internal model"}</small>
            </div>
            <div data-label="Scope">
              <strong>{system.jurisdictions.join(" · ")}</strong>
              <small>EU AI Act employment review</small>
            </div>
            <StatusBadge tone={status[system.release_status].tone}>
              {status[system.release_status].label}
            </StatusBadge>
            <Link
              href={`/systems/${system.id}`}
              aria-label={`Open ${system.name}`}
            >
              ›
            </Link>
          </article>
        ))}
      </div>
      {filtered.length === 0 && (
        <div className="empty-state">
          <h3>No system matches that evidence trail.</h3>
          <p>
            Try an owner, supplier, release status, or part of the system name.
          </p>
          <button className="fh-button" onClick={() => setQuery("")}>
            Clear filter
          </button>
        </div>
      )}
    </section>
  );
}
