# VAIC Design System (MASTER)

> Source of truth for all visual and interaction decisions. Page-specific overrides live in `pages/`. When a page file exists, its rules override this Master.

**Stack:** React 19 · Vite 8 · TypeScript 7 · Tailwind CSS 4 · TanStack Query · Lucide / Phosphor icons · Recharts + ReactFlow.

**Product context:** Enterprise AI-agent platform for Vietnamese banking — staff configure Specialist Agents, orchestrate cross-department Workflows, and generate Mini-Apps with persistent storage. Desktop-first internal pro tool.

---

## 1. Design Principles

1. **Operator, not consumer.** Every screen optimizes for the bank staff member running flows daily, not for first-time novelty. Density beats whitespace.
2. **Trust at first glance.** Banking context. Restraint over decoration. No gratuitous motion, no glassmorphism, no neon.
3. **The flow is the hero.** The Trace Dashboard and Run experience are the demo's climax — every other surface funnels toward or supports running a flow.
4. **Configurable, not hard-coded.** Every list, detail, and run view must read as "the user could rebuild this" — never as a fixed demo.
5. **Audit-grade clarity.** Every decision visible. Latencies, model names, token counts, and rationales are first-class UI, not buried in dev tools.

---

## 2. Color Tokens

Hybrid palette: **Indigo** for AI/modernity, **Slate** for banking trust, **Emerald** for success/resolution.

```css
:root {
  /* Primitive scale — Slate (base) */
  --slate-50:  #F8FAFC;
  --slate-100: #F1F5F9;
  --slate-200: #E2E8F0;
  --slate-300: #CBD5E1;
  --slate-400: #94A3B8;
  --slate-500: #64748B;
  --slate-600: #475569;
  --slate-700: #334155;
  --slate-800: #1E293B;
  --slate-900: #0F172A;
  --slate-950: #020617;

  /* Brand — Indigo */
  --indigo-50:  #EEF2FF;
  --indigo-100: #E0E7FF;
  --indigo-200: #C7D2FE;
  --indigo-500: #6366F1;
  --indigo-600: #4F46E5;
  --indigo-700: #4338CA;

  /* Status */
  --emerald-500: #10B981;  /* success, run complete */
  --emerald-600: #059669;
  --amber-500:   #F59E0B;  /* pending, human review */
  --rose-500:    #F43F5E;  /* error, escalation */
  --sky-500:     #0EA5E9;  /* running, in-flight */

  /* Semantic tokens (use these in components, never raw primitives) */
  --color-bg:             #FAFBFC;        /* app canvas */
  --color-surface:        #FFFFFF;        /* cards, panels */
  --color-surface-muted:  #F4F6F9;        /* table stripes, secondary panels */
  --color-surface-inset:  #EEF1F6;        /* code blocks, JSON viewers */
  --color-border:         #E2E8F0;
  --color-border-strong:  #CBD5E1;

  --color-text:           #0F172A;
  --color-text-secondary: #475569;
  --color-text-tertiary:  #64748B;
  --color-text-inverse:   #FFFFFF;

  --color-primary:        #4F46E5;  /* indigo-600 — AA on white */
  --color-primary-hover:  #4338CA;
  --color-primary-soft:   #EEF2FF;  /* tinted backgrounds */
  --color-on-primary:     #FFFFFF;

  --color-accent:         #059669;  /* emerald-600 — AA on white */
  --color-accent-soft:    #ECFDF5;

  --color-destructive:    #DC2626;
  --color-destructive-soft:#FEE2E2;

  --color-ring:           #6366F1;  /* focus ring */
}

[data-theme="dark"] {
  --color-bg:             #0B1120;
  --color-surface:        #0F172A;
  --color-surface-muted:  #1E293B;
  --color-surface-inset:  #020617;
  --color-border:         #1E293B;
  --color-border-strong:  #334155;

  --color-text:           #F1F5F9;
  --color-text-secondary: #CBD5E1;
  --color-text-tertiary:  #94A3B8;

  --color-primary:        #818CF8;  /* lighter indigo for dark */
  --color-primary-hover:  #A5B4FC;
  --color-primary-soft:   #1E1B4B;
  --color-on-primary:     #0F172A;

  --color-accent:         #34D399;
  --color-accent-soft:    #064E3B;
}
```

**WCAG commitments:** primary on white = 7.5:1 (AAA). Text on surface = 16:1 (AAA). Status colors never convey meaning alone — always paired with icon + label.

---

## 3. Typography

```css
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
```

| Token | Family | Size / Line | Weight | Tracking | Use |
|---|---|---|---|---|---|
| `text-display` | Plus Jakarta Sans | 32 / 40 | 700 | -0.02em | Login hero, empty-state headlines |
| `text-h1` | " | 24 / 32 | 700 | -0.01em | Page titles |
| `text-h2` | " | 20 / 28 | 600 | -0.01em | Section titles, panel headers |
| `text-h3` | " | 16 / 24 | 600 | 0 | Card titles, list headers |
| `text-body` | " | 14 / 22 | 400 | 0 | Default body |
| `text-body-strong` | " | 14 / 22 | 600 | 0 | Emphasized labels |
| `text-small` | " | 13 / 20 | 400 | 0 | Secondary info, table cells |
| `text-caption` | " | 12 / 16 | 500 | 0.02em | Tags, metadata |
| `text-mono` | JetBrains Mono | 13 / 20 | 400 | 0 | Audit entries, JSON, IDs |
| `text-mono-small` | JetBrains Mono | 12 / 18 | 400 | 0 | Inline code, tokens |

**Rules:**
- Base font size **14px** (not 16) — pro tool density.
- Tabular figures (`font-variant-numeric: tabular-nums`) for all numeric data: latencies, token counts, sequence numbers.
- No font below 12px.
- Mono is reserved for: IDs, JSON, audit entries, code, MCP envelopes, prompts.

---

## 4. Spacing & Layout

4px base scale. Dense — components live at the tighter end.

```
--space-1:  4px    --space-5:  20px
--space-2:  8px    --space-6:  24px
--space-3:  12px   --space-8:  32px
--space-4:  16px   --space-10: 40px
                    --space-12: 48px
```

**Layout primitives:**
- App shell: `256px` sidebar (collapsible to `72px` icon rail) + fluid main + optional `320px` right inspector.
- Content max-width: `1440px` standard, `1600px` for trace dashboard and tables.
- Card padding: `--space-4` (16px) standard, `--space-3` (12px) compact.
- Table row height: `40px` standard, `32px` compact.
- Border radius: `6px` controls, `8px` cards, `12px` panels/modals. **Never** fully rounded on data containers.

---

## 5. Component Primitives

### Buttons
```
[ Primary ]   bg-primary text-on-primary     — Run, Save, Submit
[ Secondary ] bg-surface border text          — Cancel, secondary actions
[ Ghost ]     bg-transparent text-secondary   — toolbar actions
[ Destructive ] bg-destructive text-white     — Delete Agent
[ Icon ]      36×36 square                    — inline actions
```
- Min height 36px (8px padding-y, 16px padding-x).
- Icon buttons **always** have `aria-label` + tooltip.
- Primary CTA is **singular per view** (Quick Reference §4: `primary-action`).

### Status Pills
Pills encode Workflow Run / Task / Agent state. **Always icon + label.**

| State | Token | Icon | Use |
|---|---|---|---|
| Pending | amber-500/soft, `Clock` | Waiting for dispatch or human review |
| Running | sky-500/soft, `Loader` (spin) | In-flight Run / Task |
| Success | emerald-500/soft, `Check` | Completed, aggregation done |
| Error | rose-500/soft, `X` | Failed, schema mismatch |
| Escalated | amber-600/soft, `AlertTriangle` | Waiting on human (FR-10) |
| Draft | slate-400/soft, `Pencil` | Unsaved config |

### Cards
```
┌─────────────────────────────┐
│ Title            [status]   │  ← h3, 16px padding
│Subtitle · meta · meta       │
├─────────────────────────────┤
│ Body content                │
└─────────────────────────────┘
```
- `1px` border `--color-border`, no shadow by default.
- Shadow `sm` only when card is interactive (clickable) or floating (dropdowns).

### Tables
- Header: `text-caption` weight 600, uppercase, slate-500.
- Row hover: `bg-surface-muted`.
- Selected row: `bg-primary-soft` with `border-l-2 border-primary`.
- **Always** a header-sticky variant for long lists.
- Bulk: checkbox column + sticky action bar (Quick Reference §8: `field-grouping`).

### Code / JSON blocks
- `bg-surface-inset`, `text-mono-small`, `padding 12px`, `border-radius 8px`.
- Inline copy button top-right.
- Syntax-highlight via `rehype-highlight` or `shiki` — keep token colors restrained.

### Forms
- Labels always visible above input (never placeholder-only — §8 `input-labels`).
- Required fields marked with `*` in `--color-destructive`.
- Helper text below input; error replaces helper text in `--color-destructive`.
- Inline validation on blur, not keystroke (§8 `inline-validation`).

---

## 6. Motion

Restrained. Motion conveys causality, not decoration (§7 `motion-meaning`).

| Interaction | Duration | Easing |
|---|---|---|
| Hover / press feedback | 120ms | ease-out |
| Modal / drawer open | 200ms | `cubic-bezier(0.16, 1, 0.3, 1)` |
| Run status transition | 240ms | ease-out |
| Trace step appears (live Run) | 180ms fade + 4px slide-up | ease-out |
| Escalation toast | 280ms slide-in from top-right | ease-out |
| Page transition (route) | 160ms cross-fade | ease-in-out |

**Mandatory:**
- `prefers-reduced-motion` freezes all animations, replaces with instant transitions (§1 `reduced-motion`).
- Trace timeline updates must be **interruptible** — new step cancels in-flight animation (§7 `interruptible`).
- Never animate `width/height/top/left` — transform and opacity only (§7 `transform-performance`).

---

## 7. Iconography

**Library:** Lucide (`lucide-react`) as primary. Stroke width **1.5px** globally. Fallback: Phosphor (regular weight).

**Semantic assignment (lock these across product):**

| Concept | Icon |
|---|---|
| Agent / Specialist | `Bot` |
| Workflow / Orchestrator | `Workflow` |
| Mini-App | `LayoutGrid` / `AppWindow` |
| Trace / Audit | `Activity` / `FileSearch` |
| Actions / Trigger | `Zap` |
| Knowledge Base | `BookOpen` / `Library` |
| Tool | `Wrench` |
| API Integration | `Plug` / `Webhook` |
| Model | `Cpu` |
| Department | `Building2` |
| Tenant | `Landmark` |
| Run | `Play` |
| Escalation | `AlertTriangle` |
| Stream / Live | `Radio` |

Never use emojis as structural icons (§4 `no-emoji-icons`). Brand logos (Anthropic, OpenAI, Google) use official SVG paths only.

---

## 8. State System (Run / Task Status)

Authoritative state vocabulary. **Same colors and icons everywhere these appear.**

```
                    ┌─────────┐
        ┌─▶ pending │ Clock   │ amber
        │           └─────────┘
        │           ┌─────────┐
        │  ▶ running│ Loader  │ sky (spin)
        │           └─────────┘
        │           ┌─────────┐
        │  ▶ success│ Check   │ emerald
        │           └─────────┘
        │           ┌─────────┐
        │  ▶ error  │ X       │ rose
        │           └─────────┘
        │           ┌─────────┐
        └─▶ escalated│ Alert  │ amber-600
                    └─────────┘
```

A Run aggregates its Tasks' statuses. Run status = `escalated` if any Task escalated; else `error` if any errored; else worst pending/running state.

---

## 9. Accessibility Commitments

- Contrast: text ≥ 4.5:1, UI glyphs ≥ 3:1, always verified independently for dark mode.
- Focus: `box-shadow: 0 0 0 2px var(--color-bg), 0 0 0 4px var(--color-ring)` — visible on any background.
- Keyboard: full nav via Tab/Shift+Tab; `Enter` activates primary; `Esc` closes modals/drawers (§1 `escape-routes`).
- ARIA: `aria-live="polite"` on Run status, trace step stream, toast region; `aria-live="assertive"` on Run errors.
- Charts: every chart has a table alternative reachable by tab. Network graph includes adjacency list panel.
- Dynamic type: respect browser font-size scaling up to 150% without layout breakage.
- Reduced motion: all animations freeze, replaced with opacity-only or instant transitions.
