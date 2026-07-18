import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Edit3, ListChecks, Plus, Sparkles, Trash2, X, XCircle } from "lucide-react";
import { getStoredUser } from "../../lib/auth";
import { auditApi } from "./api";
import type { EvaluationCriterion, EvaluationJob } from "./types";

export default function EvaluationDrawer({ sessionId, open, terminal, onClose }: {
  sessionId: string;
  open: boolean;
  terminal: boolean;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const user = getStoredUser();
  const canRun = user?.role === "manager" || user?.role === "builder";
  const criteria = useQuery({ queryKey: ["evaluation-criteria"], queryFn: auditApi.criteria, enabled: open });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<EvaluationCriterion | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);

  useEffect(() => {
    if (criteria.data && selected.size === 0) setSelected(new Set(criteria.data.map((item) => item.id)));
  }, [criteria.data, selected.size]);

  const resetEditor = () => { setEditing(null); setEditorOpen(false); setName(""); setDescription(""); };
  const refreshCriteria = () => void client.invalidateQueries({ queryKey: ["evaluation-criteria"] });
  const save = useMutation({
    mutationFn: () => editing ? auditApi.updateCriterion(editing.id, { name, description }) : auditApi.createCriterion({ name, description }),
    onSuccess: () => { resetEditor(); refreshCriteria(); },
  });
  const archive = useMutation({ mutationFn: auditApi.archiveCriterion, onSuccess: refreshCriteria });
  const run = useMutation({ mutationFn: () => auditApi.runEvaluation(sessionId, [...selected]), onSuccess: (job) => setJobId(job.id) });
  const job = useQuery<EvaluationJob>({
    queryKey: ["evaluation-job", jobId], queryFn: () => auditApi.evaluationJob(jobId!), enabled: Boolean(jobId),
    refetchInterval: (query) => ["completed", "failed"].includes(query.state.data?.status ?? "") ? false : 2000,
  });

  useEffect(() => {
    if (job.data?.status === "completed") {
      void client.invalidateQueries({ queryKey: ["audit-session", sessionId] });
      void client.invalidateQueries({ queryKey: ["latest-evaluation", sessionId] });
    }
  }, [client, job.data?.status, sessionId]);

  if (!open) return null;
  const beginEdit = (criterion: EvaluationCriterion) => { setEditing(criterion); setEditorOpen(true); setName(criterion.name); setDescription(criterion.description); };
  const toggle = (id: string) => setSelected((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const allIds = (criteria.data ?? []).map((item) => item.id);
  const running = Boolean(job.data && !["completed", "failed"].includes(job.data.status));

  return <div className="evaluation-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="evaluation-drawer" role="dialog" aria-modal="true" aria-label="Evaluate audit session">
      <header className="evaluation-drawer-header">
        <div className="evaluation-drawer-title-icon"><Sparkles /></div>
        <div><span className="audit-eyebrow">Evidence-grounded judge</span><h2>Evaluate session</h2><p>Select the quality criteria the LLM should verify against this trace.</p></div>
        <button className="audit-icon-button" onClick={onClose} aria-label="Close evaluation"><X /></button>
      </header>

      {jobId && job.data && <section className={`evaluation-progress ${job.data.status}`}>
        <div><span><strong>{job.data.phase.replaceAll("_", " ")}</strong><small>{job.data.status === "completed" ? "Quality report updated" : "The judge is processing trace evidence"}</small></span><b>{job.data.progress}%</b></div>
        <progress max={100} value={job.data.progress} />
        {job.data.status === "completed" && <p><CheckCircle2 /> Evaluation completed. The report has been refreshed.</p>}
        {job.data.status === "failed" && <p><XCircle /> {job.data.error_message || "Evaluation failed."}</p>}
      </section>}

      <section className="evaluation-criteria">
        <div className="evaluation-section-title">
          <div><span className="audit-eyebrow">Evaluation rubric</span><h3>Criteria library</h3></div>
          <span>{selected.size} of {allIds.length} selected</span>
        </div>
        <div className="evaluation-selection-actions">
          <button onClick={() => setSelected(new Set(allIds))}>Select all</button>
          <button onClick={() => setSelected(new Set())}>Clear</button>
          {canRun && <button className="evaluation-add-criterion" onClick={() => { resetEditor(); setEditorOpen(true); }}><Plus /> Add criterion</button>}
        </div>
        {criteria.isLoading && <div className="evaluation-drawer-loading">Loading criteria…</div>}
        <div className="evaluation-criterion-list">{(criteria.data ?? []).map((criterion, index) => <div className={`evaluation-criterion ${selected.has(criterion.id) ? "selected" : ""}`} key={criterion.id}>
          <label><input type="checkbox" checked={selected.has(criterion.id)} onChange={() => toggle(criterion.id)} /><span className="evaluation-criterion-index">{String(index + 1).padStart(2, "0")}</span><span><strong>{criterion.name}</strong><small>{criterion.description}</small></span></label>
          {criterion.can_edit && <div><button onClick={() => beginEdit(criterion)} aria-label={`Edit ${criterion.name}`}><Edit3 /></button><button onClick={() => archive.mutate(criterion.id)} aria-label={`Archive ${criterion.name}`}><Trash2 /></button></div>}
        </div>)}</div>
      </section>

      {canRun && editorOpen && <section className="evaluation-editor">
        <div><span className="audit-eyebrow">Criteria editor</span><h3>{editing ? "Edit criterion" : "New criterion"}</h3></div>
        <label>Name<input placeholder="Example: Output is evidence-grounded" maxLength={120} value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label>Passing condition<textarea placeholder="Describe precisely what the evaluator should verify…" maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
        <div><button className="vaic-btn vaic-btn-secondary" onClick={resetEditor}>Cancel</button><button className="vaic-btn vaic-btn-primary" disabled={!name.trim() || !description.trim() || save.isPending} onClick={() => save.mutate()}>{editing ? "Save changes" : "Add criterion"}</button></div>
      </section>}

      <footer>
        <div><ListChecks /><span><strong>{selected.size} criteria</strong><small>Overall pass requires every selected criterion to pass.</small></span></div>
        <button className="vaic-btn vaic-btn-primary" disabled={!canRun || !terminal || selected.size === 0 || run.isPending || running} onClick={() => run.mutate()}><Sparkles size={16} />{run.isPending ? "Queueing…" : running ? "Evaluation running" : "Run evaluation"}</button>
        {!terminal && <small>Evaluation is available after the session reaches a terminal state.</small>}
        {run.isError && <small className="audit-warning">{run.error.message}</small>}
      </footer>
    </aside>
  </div>;
}
