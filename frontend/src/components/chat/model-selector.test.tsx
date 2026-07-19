import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ModelSelector from "./model-selector";

const providers = [
  {
    id: "openai",
    label: "FPT AI Marketplace",
    configured: true,
    models: [{ name: "DeepSeek-V4-Flash", context_window: 128000 }],
  },
  {
    id: "google",
    label: "Google Gemini",
    configured: true,
    models: [{ name: "gemini-3.5-flash", context_window: 1000000 }],
  },
];

describe("ModelSelector", () => {
  it("renders FPT and Gemini and switches the next-message model", () => {
    const onChange = vi.fn();
    render(
      <ModelSelector
        providers={providers}
        providerId="openai"
        modelName="DeepSeek-V4-Flash"
        disabled={false}
        onChange={onChange}
      />,
    );
    expect(screen.getByText(/FPT AI Marketplace/)).toBeInTheDocument();
    expect(screen.getByText(/Google Gemini/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Mô hình AI"), {
      target: { value: "google:gemini-3.5-flash" },
    });
    expect(onChange).toHaveBeenCalledWith("google", "gemini-3.5-flash");
  });

  it("is disabled while a message is pending", () => {
    render(
      <ModelSelector
        providers={providers}
        providerId="openai"
        modelName="DeepSeek-V4-Flash"
        disabled
        onChange={() => undefined}
      />,
    );
    expect(screen.getByLabelText("Mô hình AI")).toBeDisabled();
  });
});
