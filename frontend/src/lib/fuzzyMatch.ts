/* Story 1.11 — Fuzzy match utility.
 *
 * A minimal subsequence fuzzy matcher (no third-party dependency).
 *
 * Given a query "gda":
 *   - "Go to Dashboard" matches because 'g', 'd', 'a' appear in order.
 *   - The matcher prefers:
 *       a) Exact substring matches (highest score).
 *       b) Word-boundary matches (next).
 *       c) Contiguous subsequence matches (next).
 *       d) Sparse subsequence matches (lowest, but still a hit).
 *
 * This gives a snappy Cmd+K feel without pulling in fuse.js.
 */

export interface FuzzyMatchResult {
  /** Whether the query matched the target. */
  matched: boolean;
  /** Numeric score — higher is better. 0 if no match. */
  score: number;
}

/** Empty query matches everything with a neutral score. */
const EMPTY_SCORE = 100;

/**
 * Fuzzy-match `query` against `target`. Returns a score; 0 means no match.
 *
 * The algorithm is O(n) where n = target length — fast enough for
 * the few dozen commands a command palette typically holds.
 */
export function fuzzyMatch(query: string, target: string): FuzzyMatchResult {
  const q = query.trim().toLowerCase();
  const t = target.toLowerCase();

  if (q.length === 0) {
    return { matched: true, score: EMPTY_SCORE };
  }

  // 1. Exact substring — best match.
  const substringIdx = t.indexOf(q);
  if (substringIdx !== -1) {
    // Bonus for matching at word boundary or start.
    const wordBoundaryBonus =
      substringIdx === 0 || /\s|-|_/.test(t[substringIdx - 1] ?? "") ? 50 : 20;
    return {
      matched: true,
      // Longer targets are slightly penalised so short commands bubble up.
      score: 1000 + wordBoundaryBonus - (t.length - q.length) * 2,
    };
  }

  // 2. Subsequence match — characters of `q` must appear in `t` in order.
  let qi = 0;
  let score = 0;
  let lastMatchIdx = -2; // start far so first match counts as a "gap"
  let contiguousRun = 0;
  let matchedAny = false;

  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      matchedAny = true;
      // Bonus for contiguous character runs.
      if (ti === lastMatchIdx + 1) {
        contiguousRun++;
        score += 10 + contiguousRun * 5;
      } else {
        contiguousRun = 0;
        // Bonus for matching at word boundary.
        const prevChar = t[ti - 1] ?? "";
        const isBoundary = ti === 0 || /\s|-|_/.test(prevChar);
        score += isBoundary ? 25 : 5;
      }
      // Penalty for gap since previous match.
      if (lastMatchIdx >= 0 && ti - lastMatchIdx > 1) {
        score -= (ti - lastMatchIdx - 1) * 2;
      }
      lastMatchIdx = ti;
      qi++;
    }
  }

  if (!matchedAny || qi < q.length) {
    return { matched: false, score: 0 };
  }

  // Full query consumed — small bonus for matching all of it.
  return { matched: true, score: score + 50 };
}

/** Convenience: returns true if query matches target. */
export function isFuzzyMatch(query: string, target: string): boolean {
  return fuzzyMatch(query, target).matched;
}

/**
 * Filter + sort a list of items by fuzzy match against the query.
 *
 * @param items  List of strings or objects.
 * @param query  The user's search string.
 * @param keyFn  Optional accessor to extract the matchable string from an item.
 * @returns      Items that matched, sorted by descending score.
 */
export function fuzzyFilter<T>(
  items: readonly T[],
  query: string,
  keyFn: (item: T) => string = (s) => String(s),
): Array<{ item: T; score: number }> {
  const results: Array<{ item: T; score: number }> = [];
  for (const item of items) {
    const { matched, score } = fuzzyMatch(query, keyFn(item));
    if (matched) {
      results.push({ item, score });
    }
  }
  results.sort((a, b) => b.score - a.score);
  return results;
}
