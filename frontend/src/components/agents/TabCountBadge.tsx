/* Story 2.8 T3.2 — "N documents/tools/integrations" pill (loading-aware).
 *
 * Hidden entirely while `count` is `undefined` (query still loading) so the
 * badge never flashes "0" before the real count resolves (AC #2).
 */

export type CountNoun = "document" | "tool" | "integration";

export interface TabCountBadgeProps {
  count: number | undefined;
  noun: CountNoun;
}

function pluralize(noun: CountNoun, count: number): string {
  return count === 1 ? noun : `${noun}s`;
}

export default function TabCountBadge({ count, noun }: TabCountBadgeProps) {
  if (count === undefined) return null;

  // Show just the number in the compact side-nav; the full "N documents"
  // stays available to screen readers via aria-label.
  return (
    <span
      className="vaic-tab-count-badge"
      data-testid="vaic-tab-count-badge"
      aria-label={`${count} ${pluralize(noun, count)}`}
    >
      {count}
    </span>
  );
}
