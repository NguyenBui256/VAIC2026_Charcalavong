# VAIC Design

Design artifacts for the VAIC Enterprise AI-Agent Platform. Aligns with `../prds/prd-VAIC-2026-07-17/prd/` (locked PRD) and `../architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/` (locked architecture).

## Files

| File | Purpose |
|---|---|
| `design-system.md` | **MASTER** — tokens, type, color, motion, components, a11y. Source of truth. |
| `platform-design.md` | Information architecture, app shell, per-screen wireframes, UJ wiring. |
| `pages/` *(future)* | Page-specific overrides when a screen diverges from Master. |

## How to use

1. Before implementing any screen, read `design-system.md` for tokens and primitives.
2. Open `platform-design.md §3` and find the wireframe for the screen you're building.
3. Implement in React 19 + Tailwind 4 using the tokens directly — no hardcoded hex values.
4. Validate against `design-system.md §9` (Accessibility Commitments) and the Pre-Delivery Checklist in the ui-ux-pro-max skill.

## Decisions locked

- **Style:** Refined Flat + selective Soft UI depth (not glassmorphism, not brutalism).
- **Palette:** Indigo `#4F46E5` primary + Slate `#0F172A` base + Emerald `#059669` accent.
- **Typography:** Plus Jakarta Sans (UI) + JetBrains Mono (audit/JSON/code).
- **Density:** High (8/10). Base font 14px. Table rows 40px.
- **Layout:** Desktop-first. 256px sidebar + fluid main + 320px inspector.
- **Charts:** Custom timeline + ReactFlow for collaboration graph + TanStack virtual for event streams.
- **Motion:** Restrained (4/10). 120–280ms transitions. `prefers-reduced-motion` mandatory.
