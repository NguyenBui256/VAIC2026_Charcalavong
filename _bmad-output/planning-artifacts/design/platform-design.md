# VAIC Platform Design — Screens & Flows

> Companion to `design-system.md`. All screens map to PRD FRs. Wireframes are ASCII for portability — implement in React 19 + Tailwind 4 per `design-system.md`.

**Design dials:** Variance 5/10 · Motion 4/10 · **Density 8/10**. Desktop-first, 1440–1600px target.

---

## 1. Information Architecture

Six top-level surfaces, derived directly from PRD §4 feature groups. Every surface is reachable from the persistent sidebar. The **Run** affordance is global — any Workflow can be executed from anywhere.

```
VAIC Platform
├── Dashboard              ← FR-22, FR-27  (overview, recent runs, health)
├── Agents                 ← FR-1..FR-6    (Specialist Agent CRUD)
│   ├── List
│   └── [Agent Detail]
│       ├── Identity
│       ├── Knowledge Base
│       ├── Tools
│       ├── API Integrations
│       ├── Prompt
│       └── Model
├── Workflows              ← FR-7..FR-11   (definition + Run)
│   ├── List
│   ├── [Workflow Detail]
│   │   ├── Definition
│   │   ├── Triggers       (links to Actions)
│   │   └── Runs
│   └── [Run View]         (live trace, escalation inbox)
├── Mini-Apps              ← FR-12..FR-17  (catalog + generated app)
│   ├── Catalog
│   └── [Mini-App]         (auto-provisioned UI)
├── Actions                ← FR-18..FR-20  (Schedule + Event Triggers)
│   ├── Schedule Triggers
│   └── Event Triggers
├── Audit                  ← FR-21..FR-24  (explorer + export)
│   ├── Trail explorer
│   └── [Run Trace]
│       ├── Timeline
│       └── Collaboration Graph
└── Settings
    ├── Tenant
    ├── Departments
    ├── Users & Roles
    └── Model Providers
```

**Cross-cutting overlays** (not in sidebar, surface contextually):
- **Command Palette** (`Cmd+K`) — quick nav, "Run workflow…", jump to agent.
- **Escalation Inbox** — top-right bell, opens a drawer of pending human-review items (FR-10).
- **Tenant / Department switcher** — top-left in the topbar, persistent.

---

## 2. App Shell

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [VAIC◈]  Tenant: SHB Demo ▾  /  Dept: Credit ▾          [⚡ Run ▾] [🔔 3] [ avatar ▾ ] │
├──────────┬──────────────────────────────────────────────────────────────────┤
│ DASHBOARD│                                                                  │
│ AGENTS   │                                                                  │
│ WORKFLOWS│              Main content area                                   │
│ MINI-APPS│              (page-specific, see §3)                             │
│ ACTIONS  │                                                                  │
│ AUDIT    │                                                                  │
│ ─────    │                                                                  │
│ SETTINGS │                                                                  │
│          │                                                                  │
│ [? Help] │                                                                  │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

**Sidebar (256px / collapses to 72px icon rail):**
- Each item: icon + label + optional count badge.
- Active item: `bg-primary-soft`, `text-primary`, `border-l-2 border-primary`.
- Hover: `bg-surface-muted`.
- Lock full-width by default; collapse on `< 1280px` viewport.

**Topbar (56px):**
- Left: wordmark + Tenant/Dept breadcrumb (click to switch).
- Center (optional): page title or breadcrumb trail.
- Right: global **Run** split-button (primary CTA → Run a workflow), Escalation bell with count, theme toggle, avatar menu.

**Inspector panel (320px, right, optional per page):**
- Surfaces context details without leaving the page (e.g. selected Agent summary, Audit entry detail).
- Slides in on `[` keyboard shortcut or via a "Details" toggle.

**Desktop-first commitment:** No layout work targets mobile. Mobile fallback (§7) is read-only Run status + escalation response.

---

## 3. Screen Designs

### 3.1 Dashboard

**Purpose:** First screen after login. Orients the operator — what's running, what needs me, what ran recently. Maps to FR-22 (trace preview), FR-10 (escalation surfacing), FR-27 (SPA entry).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Dashboard                                                            [Refresh]│
│ Good afternoon, Linh. 3 flows ran today. 1 needs your review.                │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌─── KPI strip ───────────────────────────────────────────────────────────┐ │
│ │ Active Runs     Pending Reviews   Mini-Apps   Token Spend (24h)         │ │
│ │   2 ◌ sky         1 ⚠ amber          14           487k  (-12% vs yest)  │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌── Needs your attention ─────────────┐  ┌── Recent Runs ────────────────┐ │
│ │ ⚠ Business Loan #LOAN-204            │  │ Business Loan Pre-Screen       │ │
│ │   Compliance vs Credit conflict       │  │ ◌ Running · 4/5 tasks · 14s    │ │
│ │   [Review decision]                   │  │ ▸ Business Loan #LOAN-203      │ │
│ │                                       │  │   ✓ Success · 22s · 14.2k tok  │ │
│ │ ⚠ KYC Refresh #KYC-118               │  │ ▸ AML Sweep Q3                 │ │
│ │   Operations flagged missing doc      │  │   ✓ Success · 1m 04s           │ │
│ │   [Review decision]                   │  │ ▸ Loan Pre-Screen #LOAN-201    │ │
│ └───────────────────────────────────────┘  │   ✗ Error · timeout · 38s     │ │
│                                            └────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌── Agents (3) ─────────────────────┐  ┌── Quick start ──────────────────┐ │
│ │ ◉ Credit Analyst    Credit  · 4 KB │  │ + New agent                    │ │
│ │ ◉ Compliance        Risk    · 2 KB │  │ + New workflow                 │ │
│ │ ◉ Operations        Ops     · 1 KB │  │ ▸ Run "Business Loan Pre-Screen"│ │
│ └────────────────────────────────────┘  └────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Design notes:**
- KPI numbers use tabular-nums; trend deltas in `--color-accent` or `--color-destructive`.
- "Needs your attention" is the escalation inbox (FR-10) — clicking opens the Run View at the conflict step.
- "Recent Runs" rows are clickable; status pill precedes title.
- Empty state: if no runs ever, show "Configure your first agent →" CTA pointing to Agent Builder.

---

### 3.2 Agent Builder

#### 3.2.1 Agent List

**FR-1, FR-6.** Tenant-scoped, Department-filtered.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Agents                                                  [+ New Agent] [Filter ▾]│
│                                                                              │
│ Filter: Department [All ▾]  Owner [All ▾]  Status [All ▾]    3 of 3          │
├────┬──────────────────────┬────────────┬─────────┬─────────┬─────────────────┤
│    │ Name                  │ Department │ Model   │ Tools   │ Updated          │
├────┼──────────────────────┼────────────┼─────────┼─────────┼─────────────────┤
│ ◉  │ Credit Analyst        │ Credit     │ Claude  │ 2 · 1KB │ 2 hours ago      │
│ ◉  │ Compliance Analyst    │ Risk       │ GPT-4o  │ 1 · 3KB │ yesterday        │
│ ◉  │ Operations Analyst    │ Operations │ Gemini  │ 1 · 1KB │ 3 days ago       │
└────┴──────────────────────┴────────────┴─────────┴─────────┴─────────────────┘
```

- Click row → Agent Detail (main panel) + Inspector shows summary card.
- Bulk select (checkbox col) → action bar appears: [Duplicate] [Archive] [Delete].
- Empty state: "Specialist Agents carry your team's expertise. [Create the first one →]".

#### 3.2.2 Agent Detail (configuration)

**FR-1 through FR-6.** Tabbed surface; each tab is one FR. Sticky tab strip + sticky footer Save bar.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ← Agents  /  Credit Analyst                  [Duplicate] […] · [Save] [Cancel]│
├──────────────────────────────────────────────────────────────────────────────┤
│ Identity  ·  Knowledge Base  ·  Tools  ·  API Integrations  ·  Prompt  ·  Model│
├──────────────────────────────────────────────────────────────────────────────┤
│  Tab: Identity                                                                │
│                                                                              │
│  Name *              [Credit Analyst                      ]                  │
│  Department *        [Credit ▾]                                              │
│  Description         [Analyses business-loan financials against policy.    ] │
│                                                                              │
│  Owner               Linh Nguyen (you)                                        │
│  Visibility          ◉ Department   ○ Tenant   ○ Private                     │
│                                                                              │
│  ── Risk indicators ──────────────────────────────────────────────────────── │
│  ☐ Allow PII in audit trail   (off by default — banking default)             │
│  ☐ Allow cross-dept KB reads  (off — FR-2 requires isolation)                │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Tab: Knowledge Base (FR-2)**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Knowledge Base                                          [Upload ⬆] [New folder]│
│                                                                              │
│ 6 documents · 247 chunks · last embedding 2h ago                             │
├──────────────────────────────────────────────────────────────────────────────┤
│  📄 SHB-Lending-Policy-2026.pdf         4.2 MB · 124 chunks · ✓ Indexed       │
│  📄 NHNN-Circular-03-2025.docx          1.8 MB ·  58 chunks · ✓ Indexed       │
│  📄 internal-credit-memo-template.md     42 KB ·  18 chunks · ✓ Indexed       │
│  📄 sbv-aml-guidance.pdf                2.1 MB ·  47 chunks · ⚠ Embedding…    │
│  ⋮                                                                           │
└──────────────────────────────────────────────────────────────────────────────┘
 └─ Test retrieval panel ──────────────────────────────────────────────────────┐
 │  Query: [How do we define a "related party" for lending?              ] [→] │
 │  → 3 passages from SHB-Lending-Policy-2026.pdf (0.84, 0.79, 0.71 sim)       │
 └─────────────────────────────────────────────────────────────────────────────┘
```

- Upload via drag-drop or button. Per-doc status: Indexed / Embedding / Failed.
- "Test retrieval" lets the operator validate the KB before saving — no agent run needed.

**Tab: Tools (FR-3)**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Tools                                                       [+ Register Tool] │
│                                                                              │
│ ┌─ financial-ratio-calculator ──────────────────────────────────────────────┐│
│ │ Input schema ✓   Output schema ✓   Embedded Python: none                  ││
│ │ Invoked: 142×   Avg latency: 240ms   Last failure: 3 days ago              ││
│ │ [Edit schema]  [Test call]  [View invocations in Audit]                    ││
│ └────────────────────────────────────────────────────────────────────────────┘│
│ ┌─ policy-lookup-retriever ─────────────────────────────────────────────────┐│
│ │ Input: query string   Output: cited passages   KB-backed                   ││
│ │ [Edit schema]  [Test call]                                                  ││
│ └────────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

Each Tool card exposes inline schema editing. JSON Schema editor uses the mono code block pattern from `design-system.md §5`.

**Tab: API Integrations (FR-4)**
- Reusable connections (Gmail stub, Calendar stub, bank-core stub).
- Card per integration: `{base_url, auth_header, status: Connected/Stub}`.
- MVP note surfaced in UI: "Demo integrations point at stubbed endpoints."

**Tab: Prompt**
- System prompt editor: mono font, line numbers, 4000 char counter.
- Variable picker: `{{tenant}}`, `{{department}}`, `{{tools.available}}`, `{{retrieval.top_k}}`.
- Per-version history in the right inspector — every save creates a version.

**Tab: Model (FR-5)**
- Picker shows available providers from Model Layer.
- Each provider: logo (official SVG), model dropdown, parameters (temperature, max tokens).
- Live "Test call" with a sample prompt — surfaces missing-provider errors at config time before they hit a Run.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Model                                                                         │
│                                                                              │
│ Provider                                                            Model    │
│ ◉ [A] Anthropic  ○ [O] OpenAI  ○ [G] Google  ○ Local Ollama                  │
│                                                                              │
│   Model:    [Claude Opus 4.6 ▾]                                               │
│   Temp:     [────●──] 0.3                                                     │
│   Tokens:   [4096]                                                            │
│                                                                              │
│   [Test with sample prompt "Hello, are you online?" →]                       │
│    → 200 OK · 312 tokens · 1.2s · Claude Opus 4.6 confirmed                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### 3.3 Workflow Orchestrator

#### 3.3.1 Workflow Detail (definition — FR-7)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ← Workflows / Business Loan Pre-Screen                  [▶ Run] [Save] […]    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Definition  ·  Triggers  ·  Runs                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  Name *       [Business Loan Pre-Screen                                  ]    │
│  Department * [Credit ▾]                                                      │
│                                                                              │
│  ┌─ Describe the flow in natural language ──────────────────────────────────┐│
│  │ Pre-screen a business loan:                                              ││
│  │  1. Pull the applicant's financial summary                               ││
│  │  2. Check credit policy compliance (Credit Analyst)                      ││
│  │  3. Check AML/KYC compliance (Compliance Analyst)                        ││
│  │  4. Verify the document checklist (Operations Analyst)                   ││
│  │  5. Return a consolidated decision + generate a case Mini-App            ││
│  │                                                                          ││
│  │ Constraints:                                                             ││
│  │  - Must cite policy for every credit/risk verdict                        ││
│  │  - Escalate to human if any two analysts disagree                        ││
│  │                                                                          ││
│  │                                                          [▶ Decompose]   ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ Preview: decomposed Tasks (read-only) ─────────────────────────────────┐ │
│  │ 1. pull-financials        → Operations Analyst   (tool: bank-core)       │ │
│  │ 2. check-credit-policy    → Credit Analyst       (KB: SHB-Lending)       │ │
│  │ 3. check-aml-kyc          → Compliance Analyst   (KB: NHNN circulars)    │ │
│  │ 4. verify-checklist       → Operations Analyst   (tool: doc-checker)     │ │
│  │ 5. aggregate-decision     → Orchestrator                             ✓     │ │
│  │ 6. emit-miniapp-schema    → Orchestrator        (→ Mini-App Builder)    │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **No visual drag-drop editor in MVP** (FR-7 explicitly out-of-scope). Text description + AI-decomposed preview instead.
- `[▶ Decompose]` is a non-mutating preview — operator sees what the Orchestrator would emit before saving.

#### 3.3.2 Run View (live — FR-8, FR-9, FR-10, FR-22)

The climax surface. Two panes: run header + steps list (left), live step detail (right).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ◀ Back to Workflow   Run #RUN-2026-0717-1432-2          ◌ Running · 14s [Stop]│
│ Business Loan Pre-Screen · applicant: SHB-LOAN-204                           │
│ Token spend: 8.4k / 50k   ·   Triggered by: Linh (manual)                    │
├────────────────────────────────────────┬─────────────────────────────────────┤
│ STEPS                                  │ STEP DETAIL                          │
│                                        │                                      │
│ ✓ Orchestrator decomposed      0.4s    │ check-credit-policy                  │
│   └ 6 tasks emitted                    │ ◌ Running · Credit Analyst · 4.2s    │
│                                        │                                      │
│ ✓ pull-financials              2.1s    │ Agent: Credit Analyst                │
│   → Operations Analyst                 │ Model: Claude Opus 4.6               │
│   bank-core returned 14 fields         │ Tools: financial-ratio-calculator    │
│                                        │ KB retrieved: 3 passages (0.84 sim)  │
│ ◌ check-credit-policy          4.2s    │                                      │
│   → Credit Analyst                     │ ┌─ Latest audit entry ─────────────┐ │
│   pulling policy, ratio check…        │ │ {                                  │ │
│                                        │ │   "step_id": "step_03",            │ │
│ ◷ check-aml-kyc                —       │ │   "agent": "credit-analyst",       │ │
│   → Compliance Analyst (queued)        │ │   "tool": "fin-ratio-calc",        │ │
│                                        │ │   "input": { "summary": {...} },   │ │
│ ◷ verify-checklist             —       │ │   "status": "streaming",           │ │
│   → Operations Analyst (queued)        │ │   "latency_ms": 4213               │ │
│                                        │ │ }                                  │ │
│ ◷ aggregate-decision           —       │ └────────────────────────────────────┘ │
│                                        │                                      │
│ ◷ emit-miniapp-schema          —       │ [View in Audit]   [Force retry]       │
└────────────────────────────────────────┴─────────────────────────────────────┘
```

- Steps stream in via `aria-live="polite"`. New step animates 180ms fade + slide.
- Selecting a step swaps the right pane; no page nav.
- On escalation (FR-10): step pill becomes `⚠ Escalated`, the right pane shows conflict context with a decision form:
  ```
  ┌─ Decision required ───────────────────────┐
  │ Conflict between Credit and Compliance.    │
  │ Credit: "Approve with conditions"          │
  │ Compliance: "Reject — AML flag on related  │
  │              party"                        │
  │ Suggested resolution: Escalate to manager  │
  │                                            │
  │ Your decision:                             │
  │ ◉ Approve with conditions                  │
  │ ○ Reject                                   │
  │ ○ Escalate further                         │
  │                                            │
  │ Rationale: [explain…                ]      │
  │                       [Resolve & continue] │
  └────────────────────────────────────────────┘
  ```

#### 3.3.3 Workflow Runs list

Filterable by status / department / time range. Each row is a Run; click → Run View.

---

### 3.4 Trace Dashboard (Audit / Run Trace)

**FR-22 (timeline), FR-23 (graph), FR-24 (export).** Two toggleable views of the same Audit Trail. Reachable from: Run View, Audit explorer, Dashboard recent runs.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Trace · Run #RUN-2026-0717-1432-2     [Timeline ◉ | Graph ○]    [⬇ Export JSON]│
├──────────────────────────────────────────────────────────────────────────────┤
│  Total: 24 steps · 22.4s · 14.2k tokens · 3 agents · 0 escalations           │
├──────────────────────────────────────────────────────────────────────────────┤
│  Filter: [All types ▾] [All agents ▾] [Has errors ◯]                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Timeline view:                                                              │
│                                                                              │
│  0.0s ●─ Orchestrator decomposed                                  0.4s       │
│       │  6 tasks emitted to 3 agents                                          │
│       │                                                                       │
│  0.4s ●─ pull-financials → Operations                             2.1s  ✓    │
│       │  tool: bank-core · 14 fields returned                                 │
│       │                                                                       │
│  2.5s ●─ check-credit-policy → Credit                             6.3s  ✓    │
│       │  KB: 3 passages cited · tool: fin-ratio-calc                          │
│       │  confidence: 0.82                                                     │
│       │                                                                       │
│  2.5s │ ─ check-aml-kyc → Compliance (parallel)                    4.8s  ✓    │
│       │  KB: 5 passages cited · sanctions: clean                              │
│       │                                                                       │
│  8.8s ●─ verify-checklist → Operations                            1.2s  ✓    │
│       │  6/7 docs present · 1 missing (tax return)                            │
│       │                                                                       │
│ 10.0s ●─ aggregate-decision → Orchestrator                        0.6s  ✓    │
│       │  consensus: Approve w/ conditions                                     │
│       │                                                                       │
│ 10.6s ●─ emit-miniapp-schema → Orchestrator                       1.4s  ✓    │
│          → Mini-App provisioned: "Business Loan Case #LOAN-204"               │
│          [Open Mini-App →]                                                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Collaboration graph view (toggle):**

```
                      ┌─────────────────────┐
                      │   Orchestrator       │
                      │   planner · aggregator│
                      └──────────┬──────────┘
            ┌───────────────────┼─────────────────────┐
            │                   │                     │
            ▼                   ▼                     ▼
   ┌─────────────────┐ ┌─────────────────┐  ┌──────────────────┐
   │ Credit Analyst   │ │ Compliance      │  │ Operations       │
   │ ✓ check-policy   │ │ ✓ check-aml-kyc │  │ ✓ pull-financials│
   │ 6.3s · 0.82 conf │ │ 4.8s            │  │ ✓ verify-checklist│
   └─────────────────┘ └─────────────────┘  │   1.2s           │
                                            └──────────────────┘
                  ↓ (Orchestrator)
                  ▼
         ┌────────────────────────────┐
         │ Mini-App: Loan Case #204    │
         │ [Open →]                    │
         └────────────────────────────┘
```

- Implement with **ReactFlow** (or Cytoscape.js) — declarative nodes/edges, accessible list alternative below the SVG.
- Edge label: `{task_summary, status}` per FR-23.
- Click node → filters timeline to that agent's entries (keeps both views synchronized).
- Always provide **adjacency list table** below the canvas for screen-reader users (Quick Reference §10 `data-table`).

**Export (FR-24):** JSON download button in header. Adds `signed_with: tenant_audit_key` field per FR-24.

---

### 3.5 Mini-App Builder

#### 3.5.1 Catalog (FR-12–FR-17)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Mini-Apps                                              [+ Generate from Run ▾] │
│                                                                              │
│ Filter: [All departments ▾] [Visibility ▾]   14 apps                         │
├──────────────────────────┬──────────────────────────┬─────────────────────────┤
│ Business Loan Case #204   │ AML Sweep Tracker        │ KYC Refresh Queue       │
│ Credit · Need-Auth · 🟢   │ Risk · Private · 🟢      │ Ops · Need-Auth · 🟢    │
│ 12 rows · last edit 2h    │ 47 rows · 3d ago         │ 8 rows · today          │
│ [Open]  [Schema]  [Events]│ [Open]  [Schema]         │ [Open]  [Schema]        │
└──────────────────────────┴──────────────────────────┴─────────────────────────┘
```

- Each card shows Visibility Tier with colored dot (Private = slate, Need-Auth = sky, Public = emerald).
- `[Schema]` opens a read-only view of the auto-generated entity schema + UI spec (FR-12).
- `[Events]` opens the App Event feed for this `app_id` (FR-17).

#### 3.5.2 Generated Mini-App (FR-15)

Auto-rendered React UI from the Agent's emitted UI spec. Reachable at `/apps/:app_id`.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ◀ Mini-Apps  /  Business Loan Case #204        Visibility: Need-Auth · 🟢     │
├──────────────────────────────────────────────────────────────────────────────┤
│ Applicant        Amount        Status      Risk        Owner        Updated   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Thanh Nguyen     2.4B VND      ◐ Review   Medium       Linh         2h ago   │
│ Mai Tran         850M VND      ✓ Approved Low          Linh         1d ago   │
│ + Add row                                                                  │
└──────────────────────────────────────────────────────────────────────────────┘
 ┌─ Live event stream ────────────────────────────────────────────────────────┐
 │ 14:32:08  row.created     Thanh Nguyen · 2.4B VND · seq #0023                 │
 │ 14:34:15  row.updated     status → Review · seq #0024                         │
 │ 14:38:00  event.dispatched → Workflow "Post-Filing" started · seq #0025       │
 └──────────────────────────────────────────────────────────────────────────────┘
```

- Visibility Tier enforced server-side; UI never gates alone (FR-16).
- Every row edit emits an App Event visible in the stream (FR-17) — makes the closed loop tangible.
- Sequence number column makes gaps detectable (FR-20).

---

### 3.6 Actions (FR-18, FR-19, FR-20)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Actions                                                          [+ New Action]│
├──────────────────────────────────────────────────────────────────────────────┤
│  Schedule Triggers (cron)                                  2 active            │
│  ┌─────────────────────────────────┬───────────────┬────────────────────┐    │
│  │ Every weekday 09:00              │ Business Loan │ Last fire: 09:00   │    │
│  │ → Pre-Screen Batch Workflow       │ Pre-Screen    │ Next: tomorrow     │    │
│  │                                  │               │ [Pause] [Edit]     │    │
│  └─────────────────────────────────┴───────────────┴────────────────────┘    │
│                                                                              │
│  Event Triggers (on App Event)                            3 active            │
│  ┌─────────────────────────────────┬───────────────┬────────────────────┐    │
│  │ On row.created in Loan Case #204 │ Post-Filing   │ Last fire: 2h ago  │    │
│  │ Filter: amount > 1B VND           │ Workflow      │ Fires: 12×         │    │
│  │                                  │               │ [Pause] [Edit]     │    │
│  └─────────────────────────────────┴───────────────┴────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────┘
```

- Each trigger card surfaces "last fire / next fire / fire count" — makes the otherwise-invisible cron tangible.
- Event Triggers show the filter predicate in plain English: "fires when Loan Case Mini-App creates a row AND amount > 1B VND".

---

### 3.7 Audit Trail Explorer (FR-21, FR-24)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Audit Trail                                                  [⬇ Export JSON]   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Filters                                                                        │
│ Run:       [All ▾]            Agent:  [All ▾]                                  │
│ Type:      [All ▾]            Time:   [Last 24h ▾]                            │
│ Search:    [enter query…                                                  ]    │
├──────────────────────────────────────────────────────────────────────────────┤
│ 14:38:00.234  run.started       RUN-2026-0717-1432-2  Linh                    │
│ 14:38:00.581  task.decomposed   6 tasks → 3 agents                            │
│ 14:38:00.612  task.dispatched   step_01 → Operations · MCP envelope #1        │
│ 14:38:02.718  task.completed    step_01 · 2106ms · bank-core · 14 fields      │
│ 14:38:02.734  task.dispatched   step_02 → Credit · MCP envelope #2            │
│ 14:38:02.740  kb.retrieved      Credit · 3 passages · 0.84/0.79/0.71          │
│ 14:38:08.944  model.invoked     Claude Opus 4.6 · 1.8k in · 412 out · 6.2s    │
│  ⋮                                                                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

- Rows are append-only — no edit affordance anywhere (FR-21 invariant).
- Clicking a row opens the inspector with the full JSON entry.
- Token counter sums across all `model.invoked` rows in the current filter — surfaces the NFR §8.2 cost guardrail.

---

## 4. User Journey Wiring

### UJ-1 — Linh configures end-to-end (PRD §2.3)

| Step | Screen | FR |
|---|---|---|
| Open Agent Builder | §3.2.1 → click "+ New Agent" | FR-1 |
| Create Credit Analyst | §3.2.2 Identity tab | FR-1, FR-6 |
| Upload policy PDFs | §3.2.2 KB tab, drag-drop | FR-2 |
| Configure 2 tools | §3.2.2 Tools tab | FR-3 |
| Register API integration | §3.2.2 API tab | FR-4 |
| Pick Claude model | §3.2.2 Model tab, live test | FR-5 |
| Repeat for Compliance, Operations | §3.2.1 list | FR-1..6 |
| Open Workflow Orchestrator | §3.3.1 | FR-7 |
| Describe flow in NL, Decompose preview | §3.3.1 | FR-8 |
| Click Run | §3.3.2 Run View | FR-9 |
| Watch Trace populate live | §3.4 timeline | FR-22 |
| Open generated Mini-App | §3.5.2 | FR-12..17 |

### UJ-2 — Judge watches one configured flow (PRD §2.3)

| Step | Screen | FR |
|---|---|---|
| One-sentence description | Topbar Run button context | FR-27 |
| Request submitted to Orchestrator | §3.3.2 Run View | FR-8 |
| Trace populates: decompose → dispatch → tool → aggregate → escalate | §3.4 | FR-22, FR-23 |
| Open generated Mini-App, edit a row | §3.5.2 | FR-15 |
| Watch edit emit event → fire Workflow | §3.5.2 event stream + §3.3.2 | FR-17, FR-19 |

---

## 5. States

### Empty states
Every list/table has a genuine empty state with a one-line explanation + primary action:
- No agents: "Specialist Agents carry your team's expertise. [+ Create the first one]"
- No workflows: "Workflows describe what should happen. [+ Describe your first flow]"
- No runs: "Once a workflow runs, every step lands here. ▸ Run a workflow"

### Loading states (Quick Reference §3)
- Lists/tables: skeleton rows, not spinners.
- Run View streaming: progressive disclosure, never blank pane.
- Trace graph render: skeleton nodes pulse (respect reduced-motion).

### Error states
- Inline form errors below the field (§8 `error-placement`).
- Run errors: replace Run status pill with `✗ Error`, surface cause in Run header with retry CTA.
- API errors: toast top-right with action label "Retry" / "View in audit".

---

## 6. Command Palette (`Cmd+K`)

Global quick-action surface. Reduces nav clicks for power users (operators running flows daily).

```
┌──────────────────────────────────────────────────┐
│ 🔍 Search or jump…                                │
├──────────────────────────────────────────────────┤
│ ▶ Run workflow…           ⏎                       │
│ + New agent              ⌘N                        │
│ + New workflow           ⌘⇧N                      │
│ → Jump to: Credit Analyst                          │
│ → Jump to: Trace · Run #RUN-…1432-2               │
│ ⚠ Open escalation inbox (1)                       │
└──────────────────────────────────────────────────┘
```

Keyboard shortcuts (visible in palette, learned over time):
- `Cmd+K` palette · `Cmd+N` new agent · `Cmd+Shift+N` new workflow
- `R` run current workflow · `[` toggle inspector · `?` shortcuts help

---

## 7. Mobile Fallback (read-only)

Out of MVP scope (FR-27) but **acknowledged**: a narrow-viewport fallback shows only:
- Run status badge + last updated.
- Escalation response form (FR-10) — so a manager can resolve on the go.
- Audit Trail recent entries (read-only).

No config / no Mini-App editing on mobile. Surface a banner: "VAIC is optimized for desktop."

---

## 8. Implementation Notes

- **Stack alignment (Stack.md):** React 19 + Vite 8 + TS 7 + Tailwind 4 + TanStack Query.
- **Charts:** Timeline = custom React + Recharts for sparklines. Collaboration graph = **ReactFlow** (accessible, declarative, fits React 19). Event stream = virtualized list (`@tanstack/react-virtual`).
- **State:** TanStack Query for all server state. Local UI state (selected tab, drawer open) via Zustand. **Never duplicate server state into client stores.**
- **Routing:** `react-router` v7 data routers. Every Run, Agent, Mini-App has a shareable URL (FR-22 requires shareable trace).
- **Theme:** `data-theme` attribute on `<html>`, CSS variables from `design-system.md §2`. Toggle persisted in `localStorage`.
- **i18n hook:** Labels externalized from day one (`vi` and `en` dictionaries) even if MVP ships English — keeps the Vietnamese-language path open per §6.2 non-goal.
- **Icons:** `lucide-react` primary. Stroke width 1.5 throughout.
- **Forms:** `react-hook-form` + `zod` schemas — schemas generated from the same Pydantic models where possible.

---

## 9. Open Design Questions (for next pass)

1. **Tenant/Department switcher** — multi-tenant demo has 1 tenant. Should the switcher be hidden in MVP, or visible-but-single-option to telegraph multi-tenancy for judges?
2. **Real-time channel** — Run View streaming: WebSocket vs SSE vs TanStack Query refetch? Architecture hasn't pinned this; affects loading states.
3. **Mini-App theming** — explicitly out-of-scope (§6.2), but the auto-rendered Mini-App should still feel distinct from the host shell. Consider a subtle accent strip per Mini-App.
4. **Vietnamese labels** — ship English-only UI for MVP, or bilingual headers? PRD §6.2 says agent *output* language is prompt-controlled; UI language is undecided.
5. **Run comparison view** — when judges ask "how is this better than a chatbot?", a side-by-side of a chatbot session vs a VAIC Run trace would close the narrative. Out of MVP scope but worth a stub.
