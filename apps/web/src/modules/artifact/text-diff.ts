export type DiffLineType = 'same' | 'add' | 'remove';

export interface DiffLine {
  type: DiffLineType;
  text: string;
}

export interface DiffStats {
  added: number;
  removed: number;
  changed: boolean;
}

const MAX_DIFF_LINES = 800;

/**
 * Compute a unified-style line diff between two text strings using LCS.
 * Returns null if either side exceeds MAX_DIFF_LINES (too large to diff client-side).
 */
export function computeDiff(textA: string, textB: string): DiffLine[] | null {
  // Handle empty inputs explicitly — ''.split('\n') returns [''] not []
  if (!textA && !textB) return [];
  if (!textA) return textB.split('\n').map((text) => ({ type: 'add' as DiffLineType, text }));
  if (!textB) return textA.split('\n').map((text) => ({ type: 'remove' as DiffLineType, text }));

  const a = textA.split('\n');
  const b = textB.split('\n');

  if (a.length > MAX_DIFF_LINES || b.length > MAX_DIFF_LINES) {
    return null;
  }

  const m = a.length;
  const n = b.length;

  // Build LCS table
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] =
        a[i - 1] === b[j - 1]
          ? dp[i - 1][j - 1] + 1
          : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  // Backtrack to produce diff lines
  const result: DiffLine[] = [];
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      result.unshift({ type: 'same', text: a[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'add', text: b[j - 1] });
      j--;
    } else {
      result.unshift({ type: 'remove', text: a[i - 1] });
      i--;
    }
  }

  return result;
}

export function getDiffStats(lines: DiffLine[]): DiffStats {
  let added = 0;
  let removed = 0;
  for (const l of lines) {
    if (l.type === 'add') added++;
    else if (l.type === 'remove') removed++;
  }
  return { added, removed, changed: added > 0 || removed > 0 };
}

/**
 * Prepare content for diff based on preview kind.
 * JSON is pretty-printed for a more readable diff.
 */
export function prepareContent(content: string, previewKind: string): string {
  if (previewKind === 'json') {
    try {
      return JSON.stringify(JSON.parse(content), null, 2);
    } catch {
      return content;
    }
  }
  return content;
}
