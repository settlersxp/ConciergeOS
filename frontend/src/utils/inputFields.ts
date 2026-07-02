/**
 * Shared utilities for parsing prompt templates into input field definitions.
 *
 * Used by both ChainInputSection and PromptChainPage to avoid duplication.
 */

// Known static placeholders that should not be turned into input fields
const KNOWN_PLACEHOLDERS = new Set([
  "DATABASE_TABLES",
  "GUEST_INFORMATION",
  "ROOM_INFORMATION",
  "CURRENT_DATE",
  "AVAILABLE_TOOLS",
]);

/**
 * Infer the input type from a placeholder name.
 */
export function inferFieldType(name: string): "text" | "date" | "select" {
  if (name.includes("date") || name.includes("time")) return "date";
  if (name.includes("filter") || name.includes("status") || name.includes("type")) return "select";
  return "text";
}

export interface InputField {
  name: string;
  label: string;
  type: "text" | "date" | "select";
}

/**
 * Parse a prompt template string and extract user-facing input fields.
 *
 * Filters out:
 * - Chain result placeholders ({step_N})
 * - Static system placeholders (DATABASE_TABLES, GUEST_INFORMATION, etc.)
 * - Table.field patterns (runtime variables with dots)
 */
export function inferInputFields(template: string): InputField[] {
  const patterns: InputField[] = [];
  const regex = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(template)) !== null) {
    const name = match[1];
    if (name.startsWith("step_")) continue;
    if (KNOWN_PLACEHOLDERS.has(name.toUpperCase())) continue;
    if (name.includes(".")) continue;
    patterns.push({
      name,
      label: name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      type: inferFieldType(name),
    });
  }
  return patterns;
}