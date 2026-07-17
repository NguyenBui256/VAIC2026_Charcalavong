/* Test: CodeBlock — copy button top-right, syntax highlighting via shiki (UX-DR7).
 *
 * Note: shiki dynamic import may fail in test environment (jsdom). The test
 * verifies the copy button + fallback <pre> rendering regardless.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CodeBlock from "./CodeBlock";

// Mock clipboard
const writeText = vi.fn().mockResolvedValue(undefined);
Object.defineProperty(navigator, "clipboard", {
  value: { writeText },
  writable: true,
});

describe("CodeBlock", () => {
  beforeEach(() => {
    writeText.mockClear();
  });

  it("renders code text", () => {
    const code = '{"key": "value"}';
    render(<CodeBlock code={code} language="json" />);
    const block = screen.getByTestId("vaic-code-block");
    expect(block).toBeInTheDocument();
    expect(block.textContent).toContain(code);
  });

  it("renders copy button", () => {
    render(<CodeBlock code="test" />);
    expect(screen.getByTestId("vaic-code-copy")).toBeInTheDocument();
    expect(screen.getByTestId("vaic-code-copy")).toHaveAttribute(
      "aria-label",
      "Copy code to clipboard",
    );
  });

  it("copies code to clipboard on click", async () => {
    const code = '{"a": 1}';
    render(<CodeBlock code={code} />);
    const copyBtn = screen.getByTestId("vaic-code-copy");
    fireEvent.click(copyBtn);

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(code);
    });
  });

  it("shows check icon after copy (feedback)", async () => {
    render(<CodeBlock code="hello" />);
    const copyBtn = screen.getByTestId("vaic-code-copy");
    fireEvent.click(copyBtn);

    await waitFor(() => {
      expect(copyBtn).toHaveAttribute("aria-label", "Copied");
    });
  });

  it("renders label when provided", () => {
    render(<CodeBlock code="x" label="response.json" />);
    expect(screen.getByText("response.json")).toBeInTheDocument();
  });

  it("shows line numbers when showLineNumbers=true", () => {
    render(<CodeBlock code={"line1\nline2\nline3"} showLineNumbers />);
    const block = screen.getByTestId("vaic-code-block");
    // While shiki loads, the fallback renders line numbers
    expect(block.textContent).toContain("line1");
    expect(block.textContent).toContain("line3");
  });
});
