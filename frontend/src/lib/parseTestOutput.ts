/**
 * /validate (backend/app/services.py -> validate_repository) runs the
 * detected test command and returns only raw stdout/stderr plus a single
 * pass/fail boolean — there is no structured per-test JSON. For the pytest
 * framework specifically, pytest's own summary line and short-summary
 * "FAILED ..." lines are stable enough to parse for a nicer view. This is
 * a best-effort read of real output text, not a fabricated endpoint —
 * when the shape doesn't match, callers should fall back to the raw log.
 */
export interface TestCounts {
  passed: number;
  failed: number;
  skipped: number;
  errors: number;
  total: number;
}

export interface ParsedTestRun {
  counts: TestCounts | null;
  failedTests: string[];
  durationSeconds: number | null;
}

export function parsePytestOutput(stdout: string): ParsedTestRun {
  const counts: TestCounts = { passed: 0, failed: 0, skipped: 0, errors: 0, total: 0 };
  let matchedAny = false;

  const summaryLine = [...stdout.matchAll(/=+ (.+?) in ([\d.]+)s ?=+/g)].pop();
  let durationSeconds: number | null = null;

  const countSource = summaryLine ? summaryLine[1] : stdout;

  const countPattern = /(\d+)\s+(passed|failed|skipped|error|errors|xfailed|xpassed)/gi;

  for (const match of countSource.matchAll(countPattern)) {
    matchedAny = true;
    const value = parseInt(match[1], 10);
    const label = match[2].toLowerCase();

    if (label === "passed" || label === "xpassed") counts.passed += value;
    else if (label === "failed") counts.failed += value;
    else if (label === "skipped" || label === "xfailed") counts.skipped += value;
    else counts.errors += value;
  }

  if (summaryLine) {
    durationSeconds = parseFloat(summaryLine[2]);
  }

  counts.total = counts.passed + counts.failed + counts.skipped + counts.errors;

  const failedTests = [...stdout.matchAll(/^FAILED\s+(\S+)/gm)].map((m) => m[1]);

  return {
    counts: matchedAny ? counts : null,
    failedTests,
    durationSeconds,
  };
}
