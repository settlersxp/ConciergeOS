import type { DiffOp, DiffResult } from "../types";

function escapeHtml(str: string): string {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/**
 * LCS-based line diff.
 * Returns HTML for left and right panels with diff highlighting.
 * For large inputs (>300 lines), falls back to plain display.
 */
export function computeLineDiff(textA: string, textB: string): DiffResult {
  const linesA = textA.split("\n");
  const linesB = textB.split("\n");
  const m = linesA.length;
  const n = linesB.length;

  // For large inputs, fall back to plain display without diff
  if (m > 300 || n > 300) {
    return {
      left: escapeHtml(textA),
      right: escapeHtml(textB),
    };
  }

  // Build DP table for LCS
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    Array(n + 1).fill(0)
  );

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (linesA[i - 1] === linesB[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to build diff operations
  const ops: DiffOp[] = [];
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && linesA[i - 1] === linesB[j - 1]) {
      ops.unshift({ type: "common", line: linesA[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      ops.unshift({ type: "added", line: linesB[j - 1] });
      j--;
    } else {
      ops.unshift({ type: "removed", line: linesA[i - 1] });
      i--;
    }
  }

  // Build side-by-side HTML
  let leftHtml = "";
  let rightHtml = "";
  let opIdx = 0;

  while (opIdx < ops.length) {
    if (ops[opIdx].type === "common") {
      const h = `<span class="diff-common">${escapeHtml(ops[opIdx].line)}</span>`;
      leftHtml += h + "\n";
      rightHtml += h + "\n";
      opIdx++;
    } else {
      // Collect contiguous block of removed/added lines
      const removedLines: string[] = [];
      const addedLines: string[] = [];
      while (opIdx < ops.length && ops[opIdx].type !== "common") {
        if (ops[opIdx].type === "removed") {
          removedLines.push(ops[opIdx].line);
        } else {
          addedLines.push(ops[opIdx].line);
        }
        opIdx++;
      }

      // Render block: left gets removed, right gets added, pad shorter side
      const maxLen = Math.max(removedLines.length, addedLines.length);
      for (let k = 0; k < maxLen; k++) {
        if (k < removedLines.length) {
          leftHtml +=
            `<span class="diff-removed">${escapeHtml(removedLines[k])}</span>\n`;
        } else {
          leftHtml += "\n";
        }
        if (k < addedLines.length) {
          rightHtml +=
            `<span class="diff-added">${escapeHtml(addedLines[k])}</span>\n`;
        } else {
          rightHtml += "\n";
        }
      }
    }
  }

  return { left: leftHtml, right: rightHtml };
}

/**
 * Extract JSON from a text block (handle cases where JSON is embedded in markdown or other content).
 */
function extractJson(text: string): string | null {
  if (!text) return null;
  
  // Try parsing the whole text first
  const trimmed = text.trim();
  if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || 
      (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
    try {
      JSON.parse(trimmed);
      return trimmed;
    } catch {
      // Not valid JSON, try to extract
    }
  }
  
  // Try to find JSON between markdown code blocks
  const jsonBlockMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (jsonBlockMatch) {
    try {
      JSON.parse(jsonBlockMatch[1].trim());
      return jsonBlockMatch[1].trim();
    } catch {
      // Not valid JSON
    }
  }
  
  // Try to find the outermost JSON object
  const braceMatch = text.match(/\{[\s\S]*\}/);
  if (braceMatch) {
    try {
      JSON.parse(braceMatch[0]);
      return braceMatch[0];
    } catch {
      // Not valid JSON
    }
  }
  
  return null;
}

/**
 * Recursively compare two JSON values and generate highlighted HTML for the ground truth.
 * Keys/values that are missing or differ in the LLM response will be highlighted in red.
 */
function renderJsonDiff(gt: unknown, llm: unknown, indent: number): string {
  const pad = "  ".repeat(indent);
  const gtObj = gt as Record<string, unknown>;
  const llmObj = llm as Record<string, unknown>;

  if (gt === null || gt === undefined) {
    return `<span class="diff-missing">${escapeHtml(String(gt))}</span>`;
  }

  if (typeof gt !== "object") {
    // Primitive value
    if (llm !== undefined && typeof llm !== "object") {
      if (String(gt) === String(llm)) {
        return escapeHtml(String(gt));
      } else {
        return `<span class="diff-mismatch">${escapeHtml(String(gt))}</span>`;
      }
    } else if (llm === null || llm === undefined) {
      return `<span class="diff-missing">${escapeHtml(String(gt))}</span>`;
    } else {
      return `<span class="diff-missing">${escapeHtml(String(gt))}</span>`;
    }
  }

  if (Array.isArray(gt)) {
    if (gt.length === 0) return "[]";
    const lines: string[] = ["["];
    for (const item of gt) {
      const itemStr = renderJsonDiff(item, undefined, indent + 1);
      lines.push(`${pad}  ${itemStr},`);
    }
    lines.push(`${pad}]`);
    return lines.join("\n");
  }

  // Object
  if (typeof gt !== "object") {
    return escapeHtml(String(gt));
  }

  const keys = Object.keys(gtObj);
  if (keys.length === 0) return "{}";

  const lines: string[] = ["{"];
  for (const key of keys) {
    const gtVal = gtObj[key];
    const llmVal = llmObj ? llmObj[key] : undefined;

    const keyEscaped = escapeHtml(key);
    const colonSpace = ": ";

    if (llmVal === undefined) {
      // Key missing entirely in LLM response
      const valStr = renderJsonValue(gtVal, undefined, indent + 1);
      lines.push(`${pad}  <span class="diff-missing">${keyEscaped}${colonSpace}${valStr}</span>,`);
    } else {
      // Key exists in both
      if (typeof gtVal === "object" && gtVal !== null && 
          typeof llmVal === "object" && llmVal !== null) {
        // Both are objects/arrays - render recursively
        const valStr = renderJsonDiff(gtVal, llmVal, indent + 1);
        lines.push(`${pad}  ${keyEscaped}${colonSpace}${valStr},`);
      } else if (String(gtVal) === String(llmVal)) {
        // Same primitive values
        const valStr = escapeHtml(JSON.stringify(gtVal));
        lines.push(`${pad}  ${keyEscaped}${colonSpace}${valStr},`);
      } else {
        // Different values - highlight the GT value in red
        const valStr = escapeHtml(JSON.stringify(gtVal));
        lines.push(`${pad}  ${keyEscaped}${colonSpace}<span class="diff-mismatch">${valStr}</span>,`);
      }
    }
  }
  lines.push(`${pad}}`);
  return lines.join("\n");
}

function renderJsonValue(gt: unknown, llm: unknown, indent: number): string {
  const pad = "  ".repeat(indent);
  if (typeof gt !== "object" || gt === null) {
    if (llm === undefined) {
      return `<span class="diff-missing">${escapeHtml(JSON.stringify(gt))}</span>`;
    }
    if (String(gt) !== String(llm)) {
      return `<span class="diff-mismatch">${escapeHtml(JSON.stringify(gt))}</span>`;
    }
    return escapeHtml(JSON.stringify(gt));
  }
  if (Array.isArray(gt)) {
    if (gt.length === 0) return "[]";
    const lines: string[] = ["["];
    for (const item of gt) {
      const itemStr = renderJsonValue(item, undefined, indent + 1);
      lines.push(`${pad}  ${itemStr},`);
    }
    lines.push(`${pad}]`);
    return lines.join("\n");
  }
  return renderJsonDiff(gt, llm, indent);
}

/**
 * Compute a JSON diff between ground truth and LLM response.
 * Returns HTML for the left (ground truth) and right (LLM response) panels.
 * The left panel will have red highlighting for keys/values missing or different in the LLM response.
 */
export function computeJsonDiff(groundTruth: string | null, llmResponse: string | null): DiffResult {
  if (!groundTruth && !llmResponse) {
    return {
      left: "(no ground truth)",
      right: "(no response)",
    };
  }

  if (!groundTruth) {
    return {
      left: "(no ground truth)",
      right: escapeHtml(llmResponse || "(no response)"),
    };
  }

  if (!llmResponse) {
    // Entire response is missing - highlight all ground truth in red
    const gtJson = extractJson(groundTruth);
    if (gtJson) {
      return {
        left: `<span class="diff-missing">${escapeHtml(gtJson)}</span>`,
        right: "(no response)",
      };
    }
    return {
      left: `<span class="diff-missing">${escapeHtml(groundTruth)}</span>`,
      right: "(no response)",
    };
  }

  // Try to extract JSON from both
  const gtJson = extractJson(groundTruth);
  const llmJson = extractJson(llmResponse);

  if (gtJson && llmJson) {
    try {
      const gtParsed = JSON.parse(gtJson);
      const llmParsed = JSON.parse(llmJson);

      const leftHtml = renderJsonDiff(gtParsed, llmParsed, 0);
      return {
        left: leftHtml,
        right: escapeHtml(llmJson),
      };
    } catch {
      // Fall back to plain display
      return {
        left: escapeHtml(groundTruth),
        right: escapeHtml(llmResponse),
      };
    }
  }

  // If one side isn't valid JSON, fall back to plain display
  return {
    left: escapeHtml(groundTruth),
    right: escapeHtml(llmResponse),
  };
}