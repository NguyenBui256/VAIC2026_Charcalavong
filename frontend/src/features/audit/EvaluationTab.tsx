import { useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Gauge,
  Lightbulb,
  ListChecks,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";
import { getStoredUser } from "../../lib/auth";
import type { AuditEvaluation, AuditSession, EvaluationCriterionResult } from "./types";

type Evidence = { span_id?: string; event_sequence?: number; payload_sha256?: string };
type Filter = "all" | "passed" | "failed";

export default function EvaluationTab({ session, onEvaluate, onEvidence }: {
  session: AuditSession;
  onEvaluate: () => void;
  onEvidence: (evidence: Evidence) => void;
}) {
  const evaluation = session.latest_evaluation;
  const canEvaluate = ["manager", "builder"].includes(getStoredUser()?.role ?? "");
  const terminal = ["completed", "failed", "timed_out", "cancelled"].includes(session.status);

  if (!evaluation) {
    return <section className="evaluation-empty">
      <div className="evaluation-empty-icon"><Sparkles /></div>
      <span className="audit-eyebrow">Session quality</span>
      <h2>No evaluation yet</h2>
      <p>Run an evidence-grounded LLM review to validate this trace against your tenant criteria.</p>
      {canEvaluate && <button className="vaic-btn vaic-btn-primary" disabled={!terminal} onClick={onEvaluate}><Sparkles size={16} /> Evaluate session</button>}
      {!terminal && <small>The session must reach a terminal state before it can be evaluated.</small>}
    </section>;
  }

  return <EvaluationReport evaluation={evaluation} canEvaluate={canEvaluate} onEvaluate={onEvaluate} onEvidence={onEvidence} />;
}

function EvaluationReport({ evaluation, canEvaluate, onEvaluate, onEvidence }: {
  evaluation: AuditEvaluation;
  canEvaluate: boolean;
  onEvaluate: () => void;
  onEvidence: (evidence: Evidence) => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const passedCount = evaluation.criteria.filter((item) => item.passed).length;
  const failedCount = evaluation.criteria.length - passedCount;
  const score = Math.round(Number(evaluation.score ?? 0) * 100);
  const filteredCriteria = useMemo(
    () => evaluation.criteria.filter((item) => filter === "all" || (filter === "passed" ? item.passed : !item.passed)),
    [evaluation.criteria, filter],
  );

  return <div className="evaluation-report">
    <header className="evaluation-report-header">
      <div>
        <span className="audit-eyebrow"><Sparkles size={13} /> Latest LLM evaluation</span>
        <h2>Session quality report</h2>
        <p>Evidence-grounded assessment at {new Date(evaluation.created_at).toLocaleString()}.</p>
      </div>
      {canEvaluate && <button className="vaic-btn vaic-btn-secondary" onClick={onEvaluate}><RefreshCw size={16} /> Re-evaluate</button>}
    </header>

    <section className={`evaluation-hero ${evaluation.overall_pass ? "is-pass" : "is-fail"}`}>
      <div className="evaluation-score" style={{ "--evaluation-score": `${score * 3.6}deg` } as CSSProperties}>
        <div><strong>{score}</strong><span>/ 100</span></div>
      </div>
      <div className="evaluation-verdict-copy">
        <span className={evaluation.overall_pass ? "evaluation-pass" : "evaluation-fail"}>{evaluation.overall_pass ? <CheckCircle2 /> : <XCircle />}{evaluation.overall_pass ? "All criteria passed" : `${failedCount} criteria need attention`}</span>
        <h3>{evaluation.summary}</h3>
        <p>{evaluation.assessment}</p>
      </div>
    </section>

    <section className="evaluation-metrics" aria-label="Evaluation metrics">
      <Metric icon={<ListChecks />} label="Criteria passed" value={`${passedCount} / ${evaluation.criteria.length}`} />
      <Metric icon={<BrainCircuit />} label="Judge model" value={evaluation.model || evaluation.provider} />
      <Metric icon={<Gauge />} label="Judge tokens" value={(evaluation.input_tokens + evaluation.output_tokens).toLocaleString()} />
      <Metric icon={<Clock3 />} label="Judge latency" value={formatDuration(evaluation.latency_ms)} />
    </section>

    <div className="evaluation-workspace">
      <section className="evaluation-criteria-panel">
        <header className="evaluation-section-header">
          <div><span className="audit-eyebrow">Rubric results</span><h3>Evaluation criteria</h3></div>
          <div className="evaluation-filters" aria-label="Filter criteria">
            <FilterButton active={filter === "all"} onClick={() => setFilter("all")}>All <span>{evaluation.criteria.length}</span></FilterButton>
            <FilterButton active={filter === "passed"} onClick={() => setFilter("passed")}>Passed <span>{passedCount}</span></FilterButton>
            <FilterButton active={filter === "failed"} onClick={() => setFilter("failed")}>Failed <span>{failedCount}</span></FilterButton>
          </div>
        </header>
        <div className="evaluation-criteria-results">
          {filteredCriteria.map((criterion) => <CriterionCard key={criterion.criterion_id} criterion={criterion} onEvidence={onEvidence} />)}
        </div>
      </section>

      <aside className="evaluation-findings">
        <section className="evaluation-finding-section evaluation-strengths">
          <header><ShieldCheck /><div><span className="audit-eyebrow">What worked</span><h3>Strengths</h3></div></header>
          {evaluation.strengths.length ? <ul>{evaluation.strengths.map((strength) => <li key={strength}><CheckCircle2 /> <span>{strength}</span></li>)}</ul> : <p className="evaluation-muted">No strengths were returned.</p>}
        </section>

        <section className="evaluation-finding-section">
          <header><Lightbulb /><div><span className="audit-eyebrow">Observations</span><h3>Insights</h3></div></header>
          <div className="evaluation-insight-list">{evaluation.insights.map((insight, index) => <article key={`${insight.title}-${index}`}>
            <span className={`evaluation-severity severity-${normalizeSeverity(insight.severity)}`}>{insight.severity || "insight"}</span>
            <strong>{insight.title || "Trace insight"}</strong>
            <p>{insight.description || "No description provided."}</p>
          </article>)}</div>
        </section>

        <section className="evaluation-finding-section evaluation-issues">
          <header><AlertTriangle /><div><span className="audit-eyebrow">Action required</span><h3>Issues & recommendations</h3></div></header>
          {evaluation.issues.length ? <div className="evaluation-issue-list">{evaluation.issues.map((issue, index) => <article key={`${issue.category}-${index}`}>
            <div><span className={`evaluation-severity severity-${normalizeSeverity(issue.severity)}`}>{issue.severity || "review"}</span><strong>{issue.category || "Quality issue"}</strong></div>
            <p>{issue.description || issue.impact || "No description provided."}</p>
            {issue.impact && issue.description && <small><b>Impact</b>{issue.impact}</small>}
            {issue.recommendation && <small><b>Recommended action</b>{issue.recommendation}</small>}
          </article>)}</div> : <div className="evaluation-no-issues"><CheckCircle2 /><span>No remediation issues identified.</span></div>}
        </section>
      </aside>
    </div>
  </div>;
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div>{icon}<span>{label}<strong title={value}>{value}</strong></span></div>;
}

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return <button className={active ? "active" : ""} onClick={onClick}>{children}</button>;
}

function CriterionCard({ criterion, onEvidence }: { criterion: EvaluationCriterionResult; onEvidence: (evidence: Evidence) => void }) {
  const confidence = Math.round(criterion.confidence * 100);
  return <article className={`evaluation-criterion-result ${criterion.passed ? "is-pass" : "is-fail"}`}>
    <div className="evaluation-criterion-state">{criterion.passed ? <CheckCircle2 /> : <XCircle />}</div>
    <div className="evaluation-criterion-body">
      <header><div><span>{criterion.passed ? "Passed" : "Failed"}</span><h4>{criterion.name}</h4></div><strong>{confidence}% confidence</strong></header>
      <div className="evaluation-confidence"><span style={{ width: `${confidence}%` }} /></div>
      <p>{criterion.rationale}</p>
      {!!criterion.evidence?.length && <div className="evaluation-evidence"><span>Evidence</span>{criterion.evidence.map((evidence, index) => <button key={`${evidence.span_id}-${evidence.event_sequence}-${index}`} onClick={() => onEvidence(evidence)}>
        {evidence.span_id ? `Span ${evidence.span_id.slice(0, 8)}` : evidence.event_sequence ? `Event #${evidence.event_sequence}` : `Payload ${String(evidence.payload_sha256).slice(0, 8)}`}<ArrowUpRight />
      </button>)}</div>}
    </div>
  </article>;
}

function normalizeSeverity(value?: string) {
  const severity = (value || "info").toLowerCase();
  return ["critical", "high", "medium", "low", "info"].includes(severity) ? severity : "info";
}

function formatDuration(milliseconds: number) {
  if (milliseconds < 1000) return `${milliseconds} ms`;
  const seconds = Math.round(milliseconds / 1000);
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
