# Area bug hunt

**Purpose:** find real bugs in one narrow area of the current code, including long-standing ones from early versions. This is not a diff review; review the code as it is.

**Scope:** the area and the things to look for that the request names (one line of the plan's areas file).

**Look for:**
- wrong results from realistic inputs: unusual names and characters, empty or huge collections, missing, moved or malformed files and records;
- state that goes stale: after edits, reloads, retries or undo, or when the user, request or selection changes;
- the wrong item acted on, lost input, and confirmations that act on a stale target;
- races and missing cancellation between requests, background jobs, edits and teardown;
- errors that are swallowed silently, or messages that name the wrong thing.

**Skip:** style, refactoring, performance-only and coverage findings, and bugs whose root cause lies outside the area.
