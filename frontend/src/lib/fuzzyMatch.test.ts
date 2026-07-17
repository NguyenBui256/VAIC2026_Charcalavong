/* Test: fuzzyMatch utility (Story 1.11). */

import { describe, it, expect } from "vitest";
import { fuzzyMatch, isFuzzyMatch, fuzzyFilter } from "./fuzzyMatch";

describe("fuzzyMatch", () => {
  it("matches empty query against anything with neutral score", () => {
    expect(fuzzyMatch("", "Go to Dashboard")).toEqual({
      matched: true,
      score: 100,
    });
    expect(fuzzyMatch("   ", "Agents")).toEqual({ matched: true, score: 100 });
  });

  it("returns matched: false when query is not a subsequence", () => {
    expect(fuzzyMatch("xyz", "Go to Dashboard").matched).toBe(false);
  });

  it("matches exact substring with high score", () => {
    const r = fuzzyMatch("dashboard", "Go to Dashboard");
    expect(r.matched).toBe(true);
    expect(r.score).toBeGreaterThan(1000);
  });

  it("matches subsequence", () => {
    expect(fuzzyMatch("gda", "Go to Dashboard").matched).toBe(true);
    expect(fuzzyMatch("gt", "Go to Settings").matched).toBe(true);
    expect(fuzzyMatch("as", "Agents").matched).toBe(true);
  });

  it("rewards word-boundary matches over sparse matches", () => {
    const boundary = fuzzyMatch("a", "Agents").score;
    const sparse = fuzzyMatch("a", "xxaxx").score;
    expect(boundary).toBeGreaterThan(sparse);
  });

  it("rewards contiguous runs", () => {
    const contig = fuzzyMatch("age", "Agents").score;
    const sparse = fuzzyMatch("at", "Agents").score;
    expect(contig).toBeGreaterThan(sparse);
  });

  it("rewards substring match over subsequence", () => {
    const sub = fuzzyMatch("age", "Agents").score;
    const seq = fuzzyMatch("ats", "Agents").score;
    expect(sub).toBeGreaterThan(seq);
  });

  it("prefers shorter targets for equal match", () => {
    const short = fuzzyMatch("a", "Agents").score;
    const long = fuzzyMatch("a", "Audit Actions Area").score;
    expect(short).toBeGreaterThanOrEqual(long);
  });

  it("is case-insensitive", () => {
    expect(fuzzyMatch("DASHBOARD", "Go to Dashboard").matched).toBe(true);
    expect(fuzzyMatch("dashboard", "GO TO DASHBOARD").matched).toBe(true);
    expect(fuzzyMatch("DaSh", "Dashboard").matched).toBe(true);
  });
});

describe("isFuzzyMatch", () => {
  it("returns boolean", () => {
    expect(isFuzzyMatch("agent", "Agents")).toBe(true);
    expect(isFuzzyMatch("nope", "Agents")).toBe(false);
  });
});

describe("fuzzyFilter", () => {
  it("filters and sorts items by score", () => {
    const items = ["Go to Dashboard", "Agents", "Audit"];
    const results = fuzzyFilter(items, "a");
    const names = results.map((r) => r.item);
    // All items contain 'a' (case-insensitive) — every one should match.
    expect(names).toHaveLength(3);
    // Higher-scoring items come first (Agents and Audit have 'a' at boundary).
    expect(names[0]).toMatch(/^(Agents|Audit)$/);
  });

  it("uses keyFn for objects", () => {
    const items = [
      { id: 1, label: "Go to Dashboard" },
      { id: 2, label: "Go to Agents" },
    ];
    const results = fuzzyFilter(items, "agent", (i) => i.label);
    expect(results).toHaveLength(1);
    expect(results[0].item.id).toBe(2);
  });

  it("returns empty array when nothing matches", () => {
    expect(fuzzyFilter(["Dashboard", "Agents"], "zzz")).toEqual([]);
  });

  it("returns everything with empty query, stable order by score", () => {
    const items = ["Dashboard", "Agents"];
    const results = fuzzyFilter(items, "");
    expect(results).toHaveLength(2);
    // All items get the same neutral score; sort is stable by spec.
    expect(results[0].score).toBe(100);
  });
});
