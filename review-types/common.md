# Shared rules for every review type

These rules apply to every type in this directory. Read them together with the one type file you were asked to follow.

## Before you start
- Read the repository's agent instructions (CLAUDE.md, AGENTS.md or similar) and its README first. Project conventions override generic advice: don't suggest a change that breaks them, and report code that breaks them.
- You review read-only. Unless the type file says otherwise, you don't edit, build, run tests or start the project.
- Stay in the scope the request names, such as an area, a layer, a diff or the whole project. You may follow calls outside that scope, but report only findings whose root cause lies inside it.

## What counts as a finding
- **Verify every finding** by reading the code it depends on.
  - Trace a bug from a concrete starting state to the wrong result.
  - Back an "unused" claim with a search across the code, its tests and its tools. Report "used only by tests" separately from "unused anywhere".
  - Don't report a defect you have only inferred from a name or a comment.
- **Check what is already known.** When a list of known issues is provided, don't report what an open issue already covers. If a closed issue's fix is incomplete or has regressed, report that and name the issue.
- **Code that looks dead may be planned work.** Before you call it dead, check the open roadmap issues, plan documents and comments. If it is waiting for planned work, say so instead of proposing deletion.
- **Skip intended, documented behaviour**, unless it is still harmful.
- **Skip style, naming and formatting**, unless the type file asks for them.
- **Prefer fewer, well-traced findings over many weak ones.**
  - Report at most 15 findings unless the request gives a different limit.
  - Finding nothing is a fine result; say so.

## Severity (use exactly these)
- **critical**: data loss or corruption, or a security or privacy breach, in normal use; or a crash on startup.
- **high**: a crash or hang in a common path; data loss in a plausible path; or a defect that will cause bugs soon, such as two copies of state that already disagree.
- **medium**: wrong persistent state, the wrong item acted on, lost user input, or a feature broken in a plausible path. For non-bug types: debt that makes changes in this area noticeably riskier or slower.
- **low**: an edge case or a minor effect. For non-bug types: cleanup with a clear but small payoff.

## Each finding
A finding may become an issue of its own, so write it to stand alone: someone who reads only that finding must understand it.
- A one-line title.
- Severity, and confidence: CONFIRMED (you traced it) or PLAUSIBLE (say what would confirm it).
- `file:line` for every location involved.
- Evidence: for a bug, a concrete scenario (starting state or inputs → steps → wrong result); for other types, what you found and why it matters.
- One line on the direction of the fix, plus size (S/M/L) and risk (low/med/high) for non-bug types.

## Output
Write Markdown:
- the first line the request asks for;
- at most 200 words of summary: what you checked, and what you could not check;
- last, one fenced `json` block with every finding, sorted by severity, and nothing after it:

```json
{"findings": [
  {"title": "Removing a damaged model leaves an old error on screen", "severity": "low", "confidence": "CONFIRMED",
   "body": "**Locations:** ...\n\n**Scenario:** ...\n\n**Fix:** ..."}
]}
```

- `title`: the one-line title, plain text.
- `severity`: critical, high, medium or low. `confidence`: CONFIRMED or PLAUSIBLE (the body says what would confirm it).
- `body`: the rest of the finding as Markdown: the locations, the evidence or scenario, and the fix line.
- Write the findings only in this block, and make it valid JSON (escape quotes and newlines). With no findings, write `{"findings": []}`.

Don't paste large code blocks.
