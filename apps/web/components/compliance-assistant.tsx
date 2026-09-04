"use client";

import type {
  AISystem,
  AssistantAnswer,
  KnowledgeSource,
} from "@fairhire/api-client";
import { useState } from "react";
import { createBrowserApi } from "@/lib/browser-api";

const labels = {
  fact: "Fact",
  inference: "Inference",
  recommendation: "Recommendation",
} as const;

export function ComplianceAssistant({
  systems,
  sources,
  initialAnswers,
  offline,
}: {
  systems: AISystem[];
  sources: KnowledgeSource[];
  initialAnswers: AssistantAnswer[];
  offline: boolean;
}) {
  const [systemId, setSystemId] = useState(systems[0]?.id ?? "");
  const [question, setQuestion] = useState("");
  const [answers, setAnswers] = useState(initialAnswers);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const api = createBrowserApi();

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const answer = await api.askAssistant(
        { question, ai_system_id: systemId || null },
        crypto.randomUUID(),
      );
      setAnswers((current) => [answer, ...current]);
      setQuestion("");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The answer could not be created.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="assistant-layout">
      <aside
        className="assistant-context"
        aria-label="Assistant evidence boundary"
      >
        <p className="eyebrow">Read-only boundary</p>
        <h2>What this assistant can see</h2>
        <dl>
          <div>
            <dt>Official sources</dt>
            <dd>
              {sources.filter((item) => item.source_type === "official").length}
            </dd>
          </div>
          <div>
            <dt>Organization policies</dt>
            <dd>
              {
                sources.filter(
                  (item) => item.source_type === "organization_policy",
                ).length
              }
            </dd>
          </div>
          <div>
            <dt>Project access</dt>
            <dd>Permission filtered</dd>
          </div>
          <div>
            <dt>Write tools</dt>
            <dd>None</dd>
          </div>
        </dl>
        <p className="assistant-boundary-note">
          Candidate-level records and raw resumes are outside this context.
          Source text is treated as evidence, never as instructions.
        </p>
        <div className="source-register">
          {sources.slice(0, 5).map((source) => (
            <article key={source.id}>
              <span>{source.source_type.replace("_", " ")}</span>
              <strong>{source.title}</strong>
              <small>
                Effective{" "}
                {new Date(source.effective_at).toLocaleDateString("en-GB")} ·{" "}
                {source.version}
              </small>
            </article>
          ))}
          {!sources.length && (
            <p>No authorized knowledge sources are connected.</p>
          )}
        </div>
      </aside>

      <section
        className="assistant-conversation"
        aria-labelledby="assistant-question-title"
      >
        <form onSubmit={ask} className="assistant-prompt">
          <div>
            <p className="eyebrow">Ask against governed evidence</p>
            <h2 id="assistant-question-title">Question for this review</h2>
          </div>
          <label>
            Project context
            <select
              value={systemId}
              onChange={(event) => setSystemId(event.target.value)}
            >
              <option value="">Sources only</option>
              {systems.map((system) => (
                <option value={system.id} key={system.id}>
                  {system.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Question
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Which evidence gaps prevent a stronger conclusion for this release?"
              rows={4}
              required
            />
          </label>
          <footer>
            <span>
              Answers distinguish facts, inferences and recommendations.
            </span>
            <button
              className="fh-button"
              disabled={busy || offline || question.trim().length < 3}
            >
              {busy ? "Checking citations…" : "Create cited answer"}
            </button>
          </footer>
        </form>
        {error && (
          <p className="command-feedback is-error" role="alert">
            {error}
          </p>
        )}

        <div className="answer-history" aria-live="polite">
          {answers.map((answer) => (
            <article className="assistant-answer" key={answer.id}>
              <header>
                <div>
                  <p className="eyebrow">Recorded question</p>
                  <h3>{answer.question}</h3>
                </div>
                <span>
                  {new Date(answer.created_at).toLocaleString("en-GB")}
                </span>
              </header>
              {answer.injection_detected && (
                <div className="injection-warning" role="status">
                  Instruction override detected · no project evidence was
                  disclosed or changed.
                </div>
              )}
              <div className="answer-paragraphs">
                {answer.paragraphs.map((paragraph, index) => (
                  <div
                    data-classification={paragraph.classification}
                    key={`${answer.id}-${index}`}
                  >
                    <span>{labels[paragraph.classification]}</span>
                    <p>{paragraph.text}</p>
                    {!!paragraph.citation_ids.length && (
                      <small>[{paragraph.citation_ids.join(", ")}]</small>
                    )}
                  </div>
                ))}
              </div>
              <footer className="citation-register">
                <p className="eyebrow">Citations & rule dates</p>
                {answer.citations.map((citation) => (
                  <div key={citation.id}>
                    <strong>{citation.id}</strong>
                    <span>
                      {citation.title} · {citation.locator}
                      {citation.effective_at
                        ? ` · effective ${new Date(citation.effective_at).toLocaleDateString("en-GB")}`
                        : ""}
                    </span>
                    {citation.uri && (
                      <a href={citation.uri} rel="noreferrer" target="_blank">
                        Open source ↗
                      </a>
                    )}
                  </div>
                ))}
                {!!answer.evidence_refs.length && (
                  <p>Project evidence: {answer.evidence_refs.join(" · ")}</p>
                )}
              </footer>
            </article>
          ))}
          {!answers.length && (
            <div className="empty-state assistant-empty">
              <p className="eyebrow">No unsupported certainty</p>
              <h3>Ask a question to build a cited, reviewable answer.</h3>
              <p>
                If authorized evidence is missing, the assistant returns a
                gap—not a guess.
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
