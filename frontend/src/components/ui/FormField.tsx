/* Story 1.9 — FormField primitive (UX-DR8).
 *
 * Labels always visible above inputs (never placeholder-only).
 * Required fields marked with * in --color-destructive.
 * Helper text below input; error replaces helper text in destructive color.
 * Inline validation on blur (NOT keystroke) per UX-DR8.
 */

import {
  useState,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

export interface FormFieldProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "onBlur"> {
  /** Visible label above the input (required — never placeholder-only). */
  label: string;
  /** Helper text shown below the input. Replaced by error text if present. */
  helperText?: string;
  /** Marks the field as required (renders * in destructive color). */
  required?: boolean;
  /** Validation function called on blur. Returns error string or null. */
  validate?: (value: string) => string | null;
  /** Controlled value override. */
  value?: string;
  /** Default value for uncontrolled usage. */
  defaultValue?: string;
  /** Additional className for the wrapper. */
  className?: string;
  /** Render a custom child instead of the default input. */
  children?: ReactNode;
}

export default function FormField({
  label,
  helperText,
  required = false,
  validate,
  value: controlledValue,
  defaultValue = "",
  className = "",
  children,
  id,
  ...rest
}: FormFieldProps) {
  const [internalValue, setInternalValue] = useState(defaultValue);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  const value = controlledValue ?? internalValue;

  function handleBlur() {
    setTouched(true);
    if (validate) {
      const err = validate(value);
      setError(err);
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (controlledValue === undefined) {
      setInternalValue(e.target.value);
    }
    // If there was a previous error, clear it on edit so the user isn't stuck.
    // (But we don't validate on keystroke — only on blur per UX-DR8.)
    if (error) setError(null);
  }

  const inputId = id || `vaic-field-${label.toLowerCase().replace(/\s+/g, "-")}`;
  const helperId = `${inputId}-helper`;
  const errorId = `${inputId}-error`;
  const hasError = touched && error !== null;

  return (
    <div className={`vaic-form-field ${className}`.trim()}>
      <label htmlFor={inputId} className="vaic-form-label">
        {label}
        {required && (
          <span className="vaic-form-required" aria-label="required">
            *
          </span>
        )}
      </label>
      {children ?? (
        <input
          {...rest}
          id={inputId}
          className={`vaic-form-input vaic-focusable ${hasError ? "vaic-form-input-error" : ""}`}
          required={required}
          value={value}
          onChange={handleChange}
          onBlur={handleBlur}
          aria-invalid={hasError}
          aria-describedby={hasError ? errorId : helperText ? helperId : undefined}
        />
      )}
      {hasError ? (
        <div id={errorId} className="vaic-form-error-text" role="alert">
          {error}
        </div>
      ) : helperText ? (
        <div id={helperId} className="vaic-form-helper">
          {helperText}
        </div>
      ) : null}
    </div>
  );
}
