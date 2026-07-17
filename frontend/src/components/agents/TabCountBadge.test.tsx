/* Test: TabCountBadge — loading-aware (hidden while undefined), singular/plural. */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TabCountBadge from "./TabCountBadge";

describe("TabCountBadge", () => {
  it("renders nothing while count is undefined (query still loading)", () => {
    const { container } = render(<TabCountBadge count={undefined} noun="document" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders '0 documents' once the query resolves empty (not hidden)", () => {
    render(<TabCountBadge count={0} noun="document" />);
    expect(screen.getByTestId("vaic-tab-count-badge")).toHaveTextContent("0 documents");
  });

  it("uses singular form for count===1", () => {
    render(<TabCountBadge count={1} noun="tool" />);
    expect(screen.getByTestId("vaic-tab-count-badge")).toHaveTextContent("1 tool");
  });

  it("uses plural form for count>1", () => {
    render(<TabCountBadge count={3} noun="integration" />);
    expect(screen.getByTestId("vaic-tab-count-badge")).toHaveTextContent("3 integrations");
  });
});
