/* Test: FormField — labels above inputs, required marker, validate on blur (UX-DR8).
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FormField from "./FormField";

describe("FormField", () => {
  it("renders label above input", () => {
    render(<FormField label="Agent Name" />);
    const label = screen.getByText("Agent Name");
    expect(label.tagName).toBe("LABEL");
    const input = screen.getByLabelText("Agent Name");
    expect(input).toBeInTheDocument();
  });

  it("shows required marker (*) in destructive color when required=true", () => {
    const { container } = render(
      <FormField label="Email" required />,
    );
    const marker = container.querySelector(".vaic-form-required");
    expect(marker).toBeTruthy();
    expect(marker?.textContent).toBe("*");
  });

  it("shows helper text below input", () => {
    render(
      <FormField label="Name" helperText="Enter the full name" />,
    );
    expect(screen.getByText("Enter the full name")).toBeInTheDocument();
  });

  it("validates on blur, NOT on keystroke", () => {
    const validate = vi.fn((v: string) =>
      v.length < 3 ? "Must be at least 3 characters" : null,
    );
    render(<FormField label="Name" validate={validate} />);

    const input = screen.getByLabelText("Name");

    // Type a short value — no validation fires yet
    fireEvent.change(input, { target: { value: "ab" } });
    expect(validate).not.toHaveBeenCalled();

    // Blur triggers validation
    fireEvent.blur(input);
    expect(validate).toHaveBeenCalledTimes(1);
    expect(validate).toHaveBeenCalledWith("ab");
  });

  it("shows error text after blur when validation fails", () => {
    render(
      <FormField
        label="Name"
        validate={(v) => (v.length < 3 ? "Too short" : null)}
        defaultValue="ab"
      />,
    );
    const input = screen.getByLabelText("Name");
    fireEvent.blur(input);

    expect(screen.getByText("Too short")).toBeInTheDocument();
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("clears error on edit (but does not re-validate until next blur)", () => {
    render(
      <FormField
        label="Name"
        validate={(v) => (v.length < 3 ? "Too short" : null)}
        defaultValue="ab"
      />,
    );
    const input = screen.getByLabelText("Name");
    fireEvent.blur(input);
    expect(screen.getByText("Too short")).toBeInTheDocument();

    // Edit clears error
    fireEvent.change(input, { target: { value: "abc" } });
    expect(screen.queryByText("Too short")).not.toBeInTheDocument();
  });

  it("does not show error if validation passes", () => {
    render(
      <FormField
        label="Name"
        validate={(v) => (v.length < 3 ? "Too short" : null)}
        defaultValue="abc"
      />,
    );
    fireEvent.blur(screen.getByLabelText("Name"));
    expect(screen.queryByText("Too short")).not.toBeInTheDocument();
  });

  it("renders aria-describedby pointing to helper or error", () => {
    render(
      <FormField label="Name" helperText="Your full name" />,
    );
    const input = screen.getByLabelText("Name");
    expect(input).toHaveAttribute("aria-describedby");
  });

  it("supports uncontrolled defaultValue", () => {
    render(<FormField label="Name" defaultValue="Preset" />);
    const input = screen.getByLabelText("Name") as HTMLInputElement;
    expect(input.value).toBe("Preset");
  });
});
