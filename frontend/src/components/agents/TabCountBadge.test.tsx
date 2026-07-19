/* Test: TabCountBadge — loading-aware (hidden while undefined), singular/plural. */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TabCountBadge from "./TabCountBadge";

describe("TabCountBadge", () => {
  it("renders nothing while count is undefined (query still loading)", () => {
    const { container } = render(<TabCountBadge count={undefined} noun="document" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders just the number once the query resolves empty (not hidden)", () => {
    render(<TabCountBadge count={0} noun="document" />);
    const badge = screen.getByTestId("vaic-tab-count-badge");
    expect(badge).toHaveTextContent("0");
    expect(badge).toHaveAttribute("aria-label", "0 documents");
  });

  it("uses singular form in the aria-label for count===1", () => {
    render(<TabCountBadge count={1} noun="tool" />);
    const badge = screen.getByTestId("vaic-tab-count-badge");
    expect(badge).toHaveTextContent("1");
    expect(badge).toHaveAttribute("aria-label", "1 tool");
  });

  it("uses plural form in the aria-label for count>1", () => {
    render(<TabCountBadge count={3} noun="integration" />);
    const badge = screen.getByTestId("vaic-tab-count-badge");
    expect(badge).toHaveTextContent("3");
    expect(badge).toHaveAttribute("aria-label", "3 integrations");
  });
});
