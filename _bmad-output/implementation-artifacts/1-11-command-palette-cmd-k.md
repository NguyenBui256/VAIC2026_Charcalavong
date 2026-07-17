---
baseline_commit: ec5fdd5fe5f014ac4057cd6b9ea231a0b8e46ee3
---

# Story 1.11: Command Palette (Cmd+K)

Status: done

## Story

As a **power user**,
I want **a Cmd+K palette for quick navigation and actions**,
So that **I can move through the platform without taking my hands off the keyboard**.

## Acceptance Criteria

(Sourced verbatim from `_bmad-output/planning-artifacts/epics.md` L615–L634.)

1. **AC** — Given the shell from Story 1.8, When a user presses `Cmd+K` (macOS) or `Ctrl+K` (Windows/Linux) anywhere in the app, Then a Command Palette modal opens with a search input focused.
2. **AC** — The palette shows a list of navigation commands: Go to Dashboard, Go to Agents, Go to Workflows, Go to Mini-Apps, Go to Actions, Go to Audit, Go to Settings.
3. **AC** — When the user types a query, the list filters by fuzzy match on command name.
4. **AC** — When the user selects a navigation command (Enter or click), the palette closes and the router navigates to the target route.
5. **AC** — When the user presses `Esc`, the palette closes without action (UX-DR1 escape-routes).
6. **AC** — The palette includes a placeholder "Run workflow…" command that surfaces a "No workflows yet" message until Epic 3 lands.
7. **AC** — A registry API exists so downstream epics can register their own commands (e.g., "Run workflow X" in Epic 3, "Export audit" in Epic 6).

## Tasks / Subtasks

- [x] **T1 — Fuzzy match utility** (AC: #3)
  - [x] T1.1 `src/lib/fuzzyMatch.ts` — subsequence matcher with scoring (no third-party dep)
  - [x] T1.2 `src/lib/fuzzyMatch.test.ts` — 14 tests: empty query, no-match, substring, subsequence, word-boundary bonus, contiguous-run bonus, case-insensitivity, filter + sort
- [x] **T2 — Command registry** (AC: #7)
  - [x] T2.1 `src/components/CommandPalette/CommandRegistry.ts` — `Command` interface, `CommandRegistryImpl` class with register/unregister/unregisterByPrefix/visible/list/subscribe/clear, singleton `commandRegistry`
  - [x] T2.2 `src/components/CommandPalette/navigationCommands.ts` — 7 nav targets + "Run workflow…" placeholder
- [x] **T3 — Palette state (context)** (AC: #1, #5)
  - [x] T3.1 `src/components/CommandPalette/CommandPaletteContext.tsx` — `CommandPaletteProvider` (open/close state + global Cmd/Ctrl+K listener), `useCommandPalette()` hook
  - [x] T3.2 `src/hooks/useCommandPalette.ts` — re-export hook for `hooks/` import convention
- [x] **T4 — Modal component** (AC: #1, #2, #3, #4, #5, #6)
  - [x] T4.1 `src/components/CommandPalette/CommandPalette.tsx` — modal dialog with search input, grouped command list, fuzzy filtering, keyboard nav (↑↓/Enter/Esc), focus trap (Tab), overlay click-to-close, Run workflow placeholder special-case, ARIA dialog/modal/label
  - [x] T4.2 `src/styles/motion.css` — added `vaic-palette-in` + `vaic-palette-overlay` keyframes (UX-DR9: 200ms cubic-bezier(0.16, 1, 0.3, 1), transform/opacity only)
- [x] **T5 — App integration** (AC: #1, #2)
  - [x] T5.1 `src/App.tsx` — wrap app in `<CommandPaletteProvider>`, render `<CommandPaletteRegistrations />` (registers nav commands via `useNavigate`) + `<CommandPalette />` at root
  - [x] T5.2 `src/components/Topbar.tsx` — added "Cmd K" / "Ctrl K" hint button that opens palette via `useCommandPalette().openPalette()`
- [x] **T6 — Tests (TDD)** (AC: all)
  - [x] T6.1 `src/components/CommandPalette/CommandPalette.test.tsx` — 25 tests covering open/close, nav list, fuzzy filter, Enter navigates, click navigates, keyboard nav, Run workflow placeholder + "No workflows yet" message, registry register/unregister/unregisterByPrefix/available, accessibility (role=dialog, aria-modal, aria-label)
  - [x] T6.2 `src/lib/fuzzyMatch.test.ts` — 14 tests
  - [x] T6.3 `src/components/AppShell.test.tsx` — wrapped render in `<CommandPaletteProvider>` (Topbar now uses `useCommandPalette`)
- [x] **T7 — Verify** (AC: all)
  - [x] T7.1 `npx tsc --noEmit` clean
  - [x] T7.2 `npx vitest run` → 152/152 passed (18 test files: 113 baseline + 14 fuzzyMatch + 25 CommandPalette)
  - [x] T7.3 `npm run build` succeeds in 406ms

## Dev Notes

### Architecture Compliance

- **UX-DR1 (escape routes)**: Esc closes the palette without action. Overlay click also closes. Tab is trapped within the palette.
- **UX-DR9 (motion)**: Modal open uses `cubic-bezier(0.16, 1, 0.3, 1)` at 200ms (via `durations.modal` + `easings.modal` tokens from `lib/motion.ts`). Keyframes `vaic-palette-in` and `vaic-palette-overlay` animate only `transform` and `opacity`. `prefers-reduced-motion` freeze is inherited from the existing global rule in `motion.css`.
- **UX-DR12 (accessibility)**: `role="dialog"`, `aria-modal="true"`, `aria-label="Command palette"`. Search input has `aria-label="Search commands"`. Command rows use `role="option"` + `aria-selected`. Sections use `role="group"` + `aria-label`. Focus trap cycles Tab within the palette.
- **UX-DR10 (iconography)**: lucide-react only, 1.5px stroke. Navigation command icons match the Sidebar assignments (LayoutGrid, Bot, Workflow, AppWindow, Zap, FileSearch, Settings).

### Key Design Decisions

1. **No third-party fuzzy dep**: Implemented a lightweight subsequence matcher in `lib/fuzzyMatch.ts`. Scoring rewards: substring > word-boundary subsequence > contiguous run > sparse subsequence. Sufficient for the few dozen commands a palette holds; avoids bundle bloat from fuse.js.
2. **Singleton registry + pub/sub**: `commandRegistry` is a module singleton with a `subscribe()` method. The palette subscribes while open and bumps a `registryVersion` state to trigger re-render. Downstream epics call `commandRegistry.register(cmd)` from anywhere — no React context needed for commands themselves.
3. **Navigation commands registered via `useNavigate`**: The `CommandPaletteRegistrations` component in `App.tsx` calls `registerNavigationCommands(navigate)` on mount. This keeps navigation logic framework-native (React Router) while the registry itself is UI-agnostic.
4. **"Run workflow…" placeholder special-case**: The palette intercepts the placeholder command id (`workflow.run:__placeholder__`) and shows a "No workflows yet" message instead of executing. When Epic 3 registers real workflow commands, it can unregister the placeholder via `commandRegistry.unregisterByPrefix("workflow.run:")` and register real ones.
5. **`CommandPaletteProvider` owns the Cmd/Ctrl+K listener**: Global keydown listener in the provider's `useEffect` calls `e.preventDefault()` and toggles the palette. Works on every route because the provider wraps the entire app.
6. **Topbar hint button**: Shows platform-aware shortcut label ("Cmd K" on macOS, "Ctrl K" elsewhere) and opens the palette on click. Uses `navigator.platform` detection.
7. **`registryVersion` + `isOpen` in memo deps**: The filtered list memo depends on `[query, registryVersion, isOpen]`. Without `isOpen`, the memo would cache the empty list from the closed state and not recompute when the palette opens after registration.

### Scope Boundaries

**Story 1.11 is the command palette + registry API. Do NOT implement:**
- Real workflow commands (Run workflow X) → **Epic 3**
- Export audit command → **Epic 6**
- Real agent/actions commands → **Epic 2+**

## Dev Agent Record

### Agent Model Used

Claude (via Claude Code, glm-5.2[1m] frontend session).

### Debug Log References

- **Initial memo caching bug**: The `filtered` useMemo had deps `[query, registryVersion]` but `registryVersion` only updated via registry subscription, which only ran when `isOpen=true`. When the palette opened after commands were registered, the memo returned the cached empty list from the closed state. Fixed by adding `isOpen` to the memo deps so it recomputes when the palette opens.
- **jsdom `scrollIntoView` missing**: The active-row scroll-into-view effect called `Element.prototype.scrollIntoView` which jsdom does not implement. Added a no-op stub in `src/test-setup.ts`.
- **AppShell test provider**: `Topbar` now calls `useCommandPalette()`, which requires `CommandPaletteProvider`. Wrapped the existing AppShell test render in `<CommandPaletteProvider>` to fix the 3 failing AppShell tests.
- **border/borderColor React warning**: Non-fatal warning when the active row style adds `borderColor` on top of the base `border` shorthand. Classified as cosmetic — does not affect functionality or tests.

### Completion Notes List

- **AC1 (Cmd/Ctrl+K opens palette) ✅**: Global keydown listener in `CommandPaletteProvider` toggles palette on Cmd/Ctrl+K. Search input auto-focuses on open. Verified by 4 tests in `CommandPalette.test.tsx`.
- **AC2 (7 navigation commands) ✅**: `registerNavigationCommands()` registers all 7 nav targets (Dashboard, Agents, Workflows, Mini-Apps, Actions, Audit, Settings) with matching icons. Verified by 2 tests.
- **AC3 (fuzzy filter) ✅**: `lib/fuzzyMatch.ts` implements subsequence matching with scoring. Typing filters the command list in real-time. Verified by 4 tests.
- **AC4 (Enter/click navigates) ✅**: Enter on active command or click triggers `cmd.run()` which calls `navigate(path)` + `closePalette()`. Verified by 2 tests with navigate spy.
- **AC5 (Esc closes) ✅**: Esc keydown closes the palette without action. Overlay click also closes. Verified by 1 test.
- **AC6 (Run workflow placeholder) ✅**: Placeholder command shows "No workflows yet — Epic 3 will register real workflows here." when active. Enter on placeholder does NOT close the palette. Verified by 3 tests.
- **AC7 (Registry API) ✅**: `commandRegistry.register()`, `unregister()`, `unregisterByPrefix()`, `visible()`, `subscribe()`, `clear()`. Register returns unregister function. Same-id replaces. `available=false` hides. Verified by 6 tests.

### AC Coverage Map

| AC | Design Ref | Component | Tests | Status |
|---|---|---|---|---|
| Cmd/Ctrl+K opens palette | UX-DR1, UX-DR9 | CommandPaletteContext.tsx, CommandPalette.tsx | CommandPalette.test.tsx (4) | ✅ |
| 7 navigation commands listed | UX-DR10, UX-DR14 | navigationCommands.ts, CommandPalette.tsx | CommandPalette.test.tsx (2) | ✅ |
| Fuzzy filter on type | — | lib/fuzzyMatch.ts, CommandPalette.tsx | fuzzyMatch.test.ts (14), CommandPalette.test.tsx (4) | ✅ |
| Enter/click navigates + closes | UX-DR1 | CommandPalette.tsx | CommandPalette.test.tsx (2) | ✅ |
| Esc closes without action | UX-DR1 | CommandPalette.tsx | CommandPalette.test.tsx (1) | ✅ |
| Run workflow placeholder | — | navigationCommands.ts, CommandPalette.tsx | CommandPalette.test.tsx (3) | ✅ |
| Registry API for downstream epics | — | CommandRegistry.ts | CommandPalette.test.tsx (6) | ✅ |

### File List

**Created (new):**
- `frontend/src/lib/fuzzyMatch.ts` — subsequence fuzzy matcher with scoring (no deps)
- `frontend/src/lib/fuzzyMatch.test.ts` — 14 tests
- `frontend/src/components/CommandPalette/CommandRegistry.ts` — registry singleton + pub/sub
- `frontend/src/components/CommandPalette/CommandPaletteContext.tsx` — provider + Cmd/Ctrl+K listener + useCommandPalette hook
- `frontend/src/components/CommandPalette/CommandPalette.tsx` — modal component
- `frontend/src/components/CommandPalette/CommandPalette.test.tsx` — 25 tests
- `frontend/src/components/CommandPalette/navigationCommands.ts` — 7 nav targets + Run workflow placeholder
- `frontend/src/hooks/useCommandPalette.ts` — re-export hook
- `_bmad-output/implementation-artifacts/1-11-command-palette-cmd-k.md` — this file

**Modified (existing):**
- `frontend/src/App.tsx` — wrap in CommandPaletteProvider, render CommandPaletteRegistrations + CommandPalette at root
- `frontend/src/components/Topbar.tsx` — added Cmd K / Ctrl K hint button that opens palette
- `frontend/src/styles/motion.css` — added vaic-palette-in + vaic-palette-overlay keyframes
- `frontend/src/test-setup.ts` — added scrollIntoView stub for jsdom
- `frontend/src/components/AppShell.test.tsx` — wrapped render in CommandPaletteProvider (Topbar now uses useCommandPalette)

## Change Log

- 2026-07-17: Story 1.11 implementation complete — 152/152 tests green, tsc clean, build succeeds in 406ms. Status: review.
