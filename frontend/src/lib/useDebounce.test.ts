/* Test: useDebounce — value updates only after the delay elapses. */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "./useDebounce";

describe("useDebounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebounce("a", 200));
    expect(result.current).toBe("a");
  });

  it("does not update before the delay elapses", () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 200), {
      initialProps: { value: "a" },
    });
    rerender({ value: "ab" });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(result.current).toBe("a");
  });

  it("updates to the latest value after the delay elapses", () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 200), {
      initialProps: { value: "a" },
    });
    rerender({ value: "ab" });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe("ab");
  });
});
