/* Story 2.6 T6.4 — lightweight client-side JSON Schema draft-2020-12 lint.
 *
 * Full draft-2020-12 validation is a backend concern (jsonschema.Draft202012Validator
 * at registration, T2.1) -- this is deliberately a fast, dependency-free
 * client-side pre-check (parse validity + top-level structural sanity) so
 * the Tools tab JSON Schema editors show live inline errors (AC6) without
 * bundling a full schema-validation library or monaco-editor (YAGNIscoped
 * per Dev Notes T6.6 Open Question -- see ToolEditor.tsx).
 */

const VALID_JSON_SCHEMA_TYPES = new Set([
  "object",
  "array",
  "string",
  "number",
  "integer",
  "boolean",
  "null",
]);

export interface SchemaLintResult {
  valid: boolean;
  error: string | null;
  parsed: Record<string, unknown> | null;
}

/** Parses `text` as JSON and applies a minimal structural sanity check. */
export function lintJsonSchema(text: string): SchemaLintResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    return { valid: false, error: err instanceof Error ? err.message : "Invalid JSON", parsed: null };
  }

  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return { valid: false, error: "Schema must be a JSON object", parsed: null };
  }

  const schema = parsed as Record<string, unknown>;
  const typeError = checkTypeField(schema.type);
  if (typeError) return { valid: false, error: typeError, parsed: null };

  if ("properties" in schema && (typeof schema.properties !== "object" || schema.properties === null)) {
    return { valid: false, error: "'properties' must be an object", parsed: null };
  }

  return { valid: true, error: null, parsed: schema };
}

function checkTypeField(type: unknown): string | null {
  if (type === undefined) return null;
  const types = Array.isArray(type) ? type : [type];
  for (const t of types) {
    if (typeof t !== "string" || !VALID_JSON_SCHEMA_TYPES.has(t)) {
      return `Invalid schema 'type': ${JSON.stringify(t)}`;
    }
  }
  return null;
}
