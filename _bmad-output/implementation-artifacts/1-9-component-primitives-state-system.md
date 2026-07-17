---
baseline_commit: 2687de3085877509c213f35a493939a7a7964437
---

# Story 1.9: Component Primitives & State System

Status: review

## Story

As a **frontend developer on any downstream stream**,
I want **a complete component primitive library and authoritative state system**,
So that **I can build feature surfaces with consistent UI without re-implementing basics**.

## Acceptance Criteria

(Sourced verbatim from `_bmad-output/planning-artifacts/epics.md` L556–L591.)

1. **AC (UX-DR3 Buttons)** — Button supports 5 variants: Primary, Secondary, Ghost, Destructive, Icon (36x36 with mandatory aria-label + tooltip). Min height 36px, 8px padding-y, 16px padding-x. Only one Primary CTA per view (runtime warning when >1).
2. **AC (UX-DR4 StatusPill)** — 6 states: Pending (Clock/amber), Running (Loader-spin/sky), Success (Check/emerald), Error (AlertTriangle/rose), Escalated (AlertTriangle/amber-600), Draft (Pencil/slate-400). Same icon+color mapping everywhere (UX-DR11).
3. **AC (UX-DR5 Cards)** — 1px border with --color-border, no default shadow, sm shadow when interactive.
4. **AC (UX-DR6 Tables)** — Sticky headers, row hover (bg-surface-muted), selected row (bg-primary-soft + left border), bulk action bar.
5. **AC (UX-DR7 CodeBlock)** — Copy button top-right, syntax highlighting via shiki.
6. **AC (UX-DR8 Forms)** — Labels above inputs, required marker * in destructive color, validate on blur.
7. **AC (UX-DR9 Motion)** — Durations: hover 120ms, modal 200ms, status 240ms, step 180ms, toast 280ms, route 160ms. Easing cubic-bezier(0.16, 1, 0.3, 1) for modals. prefers-reduced-motion freezes all. Only transform/opacity animated.
8. **AC (UX-DR10 Iconography)** — lucide-react only, 1.5px stroke. Semantic assignments locked in lib/icons.tsx. No emojis as structural icons.
9. **AC (UX-DR12 Accessibility)** — Focus rings visible, keyboard nav (Tab/Shift+Tab/Enter/Esc), aria-live on status components, contrast documented.

## Tasks / Subtasks

- [x] **T1 — Foundation** (AC: #7, #8)
  - [x] T1.1 `src/lib/motion.ts` — motion tokens (durations, easings, transition helper, STEP_SLIDE_DISTANCE)
  - [x] T1.2 `src/lib/icons.tsx` — locked semantic icon assignments (UX-DR10), state mapping (UX-DR11), ICON_STROKE_WIDTH
  - [x] T1.3 `src/styles/motion.css` — keyframes (step-appear, status-fade, toast-in, route-fade, spin), prefers-reduced-motion freeze
  - [x] T1.4 `src/styles/components.css` — component-level CSS (button states, pill colors, card shadows, table styles, code block, form field, tooltip, skeleton, empty/error state)
- [x] **T2 — Tooltip** (AC: #1)
  - [x] T2.1 `src/components/ui/Tooltip.tsx` — shared CSS-based tooltip, shows on hover/focus
- [x] **T3 — Button** (AC: #1)
  - [x] T3.1 `src/components/ui/Button.tsx` — 5 variants, min 36px, Icon variant wraps in Tooltip with aria-label, single-Primary-CTA runtime warning
  - [x] T3.2 `src/components/ui/Button.test.tsx` — 11 tests: each variant, onClick, leading icon, single-Primary enforcement
- [x] **T4 — StatusPill** (AC: #2)
  - [x] T4.1 `src/components/ui/StatusPill.tsx` — 6 states from locked stateMapping, spin for running, aria-live=polite
  - [x] T4.2 `src/components/ui/StatusPill.test.tsx` — 11 tests: all 6 states, icon+label, color consistency, spin, a11y
- [x] **T5 — Card** (AC: #3)
  - [x] T5.1 `src/components/ui/Card.tsx` — 1px border, no default shadow, sm shadow when interactive, keyboard activatable
  - [x] T5.2 `src/components/ui/Card.test.tsx` — 6 tests: title/subtitle/headerAction, interactive class, keyboard activation, click
- [x] **T6 — Table** (AC: #4)
  - [x] T6.1 `src/components/ui/Table.tsx` — sticky headers, row hover, selected row class, checkbox column, bulk action bar, empty state
  - [x] T6.2 `src/components/ui/Table.test.tsx` — 9 tests: headers/rows, render prop, row click, selected class, checkbox, bulk bar, empty state, toggle
- [x] **T7 — CodeBlock** (AC: #5)
  - [x] T7.1 `src/components/ui/CodeBlock.tsx` — copy button top-right, shiki lazy-load highlighting with plain fallback, line numbers, label
  - [x] T7.2 `src/components/ui/CodeBlock.test.tsx` — 6 tests: code text, copy button, clipboard copy, copy feedback, label, line numbers
- [x] **T8 — FormField** (AC: #6)
  - [x] T8.1 `src/components/ui/FormField.tsx` — label above input, required * marker, validate on blur, error replaces helper, clears on edit
  - [x] T8.2 `src/components/ui/FormField.test.tsx` — 9 tests: label, required marker, helper text, blur-only validation, error display, error clear, no error on pass, aria-describedby, defaultValue
- [x] **T9 — Auxiliary primitives** (AC: #9)
  - [x] T9.1 `src/components/ui/EmptyState.tsx` — default Inbox icon, title, description, action CTA
  - [x] T9.2 `src/components/ui/EmptyState.test.tsx` — 4 tests
  - [x] T9.3 `src/components/ui/Skeleton.tsx` — single-line + multiline skeletons, pulse animation (opacity only)
  - [x] T9.4 `src/components/ui/Skeleton.test.tsx` — 4 tests
  - [x] T9.5 `src/components/ui/ErrorState.tsx` — AlertTriangle in destructive, message + detail + retry, role=alert aria-live=assertive
  - [x] T9.6 `src/components/ui/ErrorState.test.tsx` — 5 tests
- [x] **T10 — Barrel export + integration** (AC: all)
  - [x] T10.1 `src/components/ui/index.ts` — barrel export for all primitives
  - [x] T10.2 `src/main.tsx` — import components.css + motion.css
  - [x] T10.3 `frontend/package.json` — added shiki dep
- [x] **T11 — Tests (TDD)** (AC: all)
  - [x] T11.1 `src/lib/icons.test.tsx` — 20 tests: all semantic icon locks + state mapping locks + stroke width
  - [x] T11.2 `src/lib/motion.test.ts` — 10 tests: all durations + easings + slide distance + transition helper
  - [x] T11.3 All component tests (see above)
- [x] **T12 — Verify** (AC: all)
  - [x] T12.1 `npx tsc --noEmit` clean
  - [x] T12.2 `npx vitest run` → 113/113 passed (16 test files)
  - [x] T12.3 `npm run build` succeeds in 344ms

## Dev Notes

### Architecture Compliance

- **UX-DR3 (Buttons)**: Button component supports Primary, Secondary, Ghost, Destructive, Icon. Min 36px height, 8px padding-y, 16px padding-x via `.vaic-btn` CSS class in components.css. Icon variant wraps in Tooltip, requires aria-label. Single-Primary-CTA enforced via module-level counter that fires `console.warn` in dev when >1 Primary is mounted.
- **UX-DR4/UX-DR11 (StatusPill)**: 6 states with locked icon+color mapping from `lib/icons.tsx` `stateMapping`. Running state spins via `vaic-anim-spin` class. Always icon + label (never color alone). `aria-live="polite"` for status updates.
- **UX-DR5 (Cards)**: 1px border `--color-border`, no shadow by default. `vaic-card-interactive` class adds `--shadow-sm` + hover border-color change when `interactive=true` or `onClick` present. Keyboard-activatable (Enter/Space).
- **UX-DR6 (Tables)**: Sticky headers via `position: sticky; top: 0` on `thead th`. Row hover `bg-surface-muted` via CSS. Selected row `vaic-table-row-selected` class with `bg-primary-soft` + `inset 2px 0 0 var(--color-primary)`. Checkbox column + bulk action bar with "N selected" count.
- **UX-DR7 (CodeBlock)**: Copy button positioned `absolute; top; right`. Shiki loaded lazily via dynamic `import("shiki")` — falls back to plain `<pre>` if shiki fails or while loading. Copy uses `navigator.clipboard.writeText` with `execCommand("copy")` fallback.
- **UX-DR8 (Forms)**: Labels always visible above inputs. Required `*` marker in `--color-destructive` (`.vaic-form-required`). Validation fires on blur only (not keystroke). Error replaces helper text, clears on edit.
- **UX-DR9 (Motion)**: `lib/motion.ts` exports `durations` (hover:120, modal:200, status:240, step:180, toast:280, route:160), `easings` (modal: `cubic-bezier(0.16, 1, 0.3, 1)`), `STEP_SLIDE_DISTANCE` (4px), `transition()` helper. `motion.css` defines keyframes using only `transform` and `opacity`. `prefers-reduced-motion` freezes all animations to 0.01ms.
- **UX-DR10 (Iconography)**: `lucide-react` is the only icon library. `ICON_STROKE_WIDTH = 1.5` exported and used everywhere. Semantic assignments locked in `lib/icons.tsx` `semanticIcons` map. No emojis as structural icons.
- **UX-DR12 (Accessibility)**: Focus rings via `--focus-ring` token (`box-shadow: 0 0 0 2px var(--color-bg), 0 0 0 4px var(--color-ring)`). Keyboard nav: Card (Enter/Space), Table (row click + checkbox toggle), Tooltip (focus shows). `aria-live="polite"` on StatusPill, `aria-live="assertive"` on ErrorState.

### Key Design Decisions

1. **CSS-based component styling**: All component visual states defined in `components.css` using design tokens. Components apply className hooks, keeping inline styles to a minimum (only for dynamic values from stateMapping). This ensures token consistency and keeps components.css as the visual source of truth.
2. **Module-level Primary counter**: Instead of React context (which adds complexity), a simple module-level counter tracks mounted Primary buttons. `getPrimaryCount()` and `_resetPrimaryCount()` exported for tests. The counter fires `console.warn` in dev only via `import.meta.env.DEV` check.
3. **Shiki lazy import**: `import("shiki")` inside `useEffect` so the 200KB+ highlighter only loads when a CodeBlock actually mounts. Falls back to plain `<pre>` gracefully. Uses `github-dark` theme for consistent rendering in both light/dark modes (code blocks always have dark inset background).
4. **State mapping as single source of truth**: `stateMapping` in `lib/icons.tsx` holds icon, colorVar, softVar, label, spin for each RunState. StatusPill imports from it directly. Tests verify components reference the same mapping, enforcing UX-DR11 consistency.
5. **Tooltip built from scratch**: No Radix dependency — a simple CSS-based tooltip that shows on hover/focus and hides on blur/mouseleave. Keeps bundle size lean for a hackathon demo. Respects `prefers-reduced-motion` via opacity transition freeze.

### Scope Boundaries

**Story 1.9 is the component primitive library + state system. Do NOT implement:**
- Dashboard surface (KPI strip, recent runs) → **Story 1.10**
- Command palette (Cmd+K) → **Story 1.11**
- Agent Builder, Workflow Orchestrator, Trace Dashboard → **Epic 2+**

## Dev Agent Record

### Agent Model Used

Claude (via Claude Code, glm-5.2[1m] frontend session).

### Debug Log References

- **StatusPill colorVar test**: Initial test asserted `style.color` contains "amber" but the actual value is `var(--color-pending)`. Fixed to assert against `stateMapping.pending.colorVar` directly.
- **jsdom SVG className**: `svg.className` in jsdom is `SVGAnimatedString`, not a string — test used `getAttribute("class")` instead.
- **ErrorState icon color**: Test checked `svg.parentElement.style.color` but the icon's parent is the root div (no inline color). Fixed to check `svg.style.color` directly since AlertTriangle receives the style prop.
- **overused-font warning**: Plus Jakarta Sans flagged as "overused" — classified as false positive (spec-mandated by UX-DR2, same as Story 1.8).
- **@theme lightningcss warning**: Harmless warning from existing tokens.css Tailwind v4 bridge, not introduced by this story.

### Completion Notes List

- **AC1 (UX-DR3) ✅**: Button supports 5 variants, min 36px, Icon variant has aria-label + Tooltip, single-Primary-CTA runtime warning. 11 Button tests pass.
- **AC2 (UX-DR4) ✅**: StatusPill renders 6 states with locked icon+color mapping from stateMapping. 11 StatusPill tests pass.
- **AC3 (UX-DR5) ✅**: Card has 1px border, no default shadow, sm shadow when interactive. 6 Card tests pass.
- **AC4 (UX-DR6) ✅**: Table has sticky headers, row hover, selected row, checkbox column, bulk action bar. 9 Table tests pass.
- **AC5 (UX-DR7) ✅**: CodeBlock has copy button top-right, shiki syntax highlighting (lazy-loaded with fallback). 6 CodeBlock tests pass.
- **AC6 (UX-DR8) ✅**: FormField has label above input, required * marker, validates on blur. 9 FormField tests pass.
- **AC7 (UX-DR9) ✅**: Motion tokens defined (all 6 durations + easing). Keyframes use only transform/opacity. prefers-reduced-motion freezes all. 10 motion tests pass.
- **AC8 (UX-DR10) ✅**: lucide-react only, 1.5px stroke. Semantic assignments locked in lib/icons.tsx. 20 icon tests pass.
- **AC9 (UX-DR12) ✅**: Focus rings via --focus-ring token. Keyboard nav on Card/Table/Tooltip. aria-live on StatusPill (polite) and ErrorState (assertive).

### AC Coverage Map

| AC | Design Ref | Component | Tests | Status |
|---|---|---|---|---|
| UX-DR3 Buttons | design-system.md §5 | Button.tsx | Button.test.tsx (11) | ✅ |
| UX-DR4 StatusPill | design-system.md §5 | StatusPill.tsx | StatusPill.test.tsx (11) | ✅ |
| UX-DR5 Cards | design-system.md §5 | Card.tsx | Card.test.tsx (6) | ✅ |
| UX-DR6 Tables | design-system.md §5 | Table.tsx | Table.test.tsx (9) | ✅ |
| UX-DR7 CodeBlock | design-system.md §5 | CodeBlock.tsx | CodeBlock.test.tsx (6) | ✅ |
| UX-DR8 Forms | design-system.md §5 | FormField.tsx | FormField.test.tsx (9) | ✅ |
| UX-DR9 Motion | design-system.md §6 | lib/motion.ts + motion.css | motion.test.ts (10) | ✅ |
| UX-DR10 Iconography | design-system.md §7 | lib/icons.tsx | icons.test.tsx (20) | ✅ |
| UX-DR11 State consistency | design-system.md §8 | lib/icons.tsx stateMapping | icons.test.tsx + StatusPill.test.tsx | ✅ |
| UX-DR12 Accessibility | design-system.md §9 | All components (focus ring, aria-live, keyboard) | All test files | ✅ |

### File List

**Created (new):**
- `frontend/src/components/ui/Button.tsx` — 5 variants, single-Primary enforcement
- `frontend/src/components/ui/Button.test.tsx` — 11 tests
- `frontend/src/components/ui/StatusPill.tsx` — 6 states from locked mapping
- `frontend/src/components/ui/StatusPill.test.tsx` — 11 tests
- `frontend/src/components/ui/Card.tsx` — 1px border, interactive shadow, keyboard
- `frontend/src/components/ui/Card.test.tsx` — 6 tests
- `frontend/src/components/ui/Table.tsx` — sticky headers, row hover, bulk bar
- `frontend/src/components/ui/Table.test.tsx` — 9 tests
- `frontend/src/components/ui/CodeBlock.tsx` — copy button, shiki highlighting
- `frontend/src/components/ui/CodeBlock.test.tsx` — 6 tests
- `frontend/src/components/ui/FormField.tsx` — label above, required marker, blur validation
- `frontend/src/components/ui/FormField.test.tsx` — 9 tests
- `frontend/src/components/ui/Tooltip.tsx` — shared CSS tooltip
- `frontend/src/components/ui/Tooltip.test.tsx` — 4 tests
- `frontend/src/components/ui/EmptyState.tsx` — illustration + CTA
- `frontend/src/components/ui/EmptyState.test.tsx` — 4 tests
- `frontend/src/components/ui/Skeleton.tsx` — layout-matching skeleton
- `frontend/src/components/ui/Skeleton.test.tsx` — 4 tests
- `frontend/src/components/ui/ErrorState.tsx` — error message + retry
- `frontend/src/components/ui/ErrorState.test.tsx` — 5 tests
- `frontend/src/components/ui/index.ts` — barrel export
- `frontend/src/lib/motion.ts` — motion tokens + transition helper
- `frontend/src/lib/motion.test.ts` — 10 tests
- `frontend/src/lib/icons.tsx` — locked semantic icons + state mapping
- `frontend/src/lib/icons.test.tsx` — 20 tests
- `frontend/src/styles/motion.css` — keyframes + prefers-reduced-motion
- `frontend/src/styles/components.css` — component-level CSS using tokens
- `_bmad-output/implementation-artifacts/1-9-component-primitives-state-system.md` — this file

**Modified (existing):**
- `frontend/src/main.tsx` — added import for components.css + motion.css
- `frontend/package.json` — added shiki dependency

## Change Log

- 2026-07-17: Story 1.9 implementation complete — 113/113 tests green, tsc clean, build succeeds in 344ms. Status: review.
