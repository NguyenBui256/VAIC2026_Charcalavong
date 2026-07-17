/* Story 1.11 — Hook re-export.
 *
 * Convenience hook so consumers can import from `hooks/`:
 *   import { useCommandPalette } from "../hooks/useCommandPalette";
 *
 * The actual implementation lives in CommandPalette/CommandPaletteContext.tsx.
 */

export { useCommandPalette } from "../components/CommandPalette/CommandPaletteContext";
