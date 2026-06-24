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