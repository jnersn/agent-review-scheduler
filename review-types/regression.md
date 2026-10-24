# Regression review

**Purpose:** find bugs introduced or left behind by a range of commits that have already merged, for example everything merged since the last run.

**Scope:** the commits and diff named in the request. Read the changed files, their callers and the code around them; don't stop at the diff.

**Look for:**
- regressions in callers and other entry points that the change didn't update;
- broken persistence, migrations, caching, concurrency, undo or interplay between components;
- fixes that cover some paths of the bug they target but not all of them;
- tests that pass without the fix they claim to cover;
- changes that contradict the project's documented conventions in a way that causes wrong behaviour.

**Skip:** refactoring, performance-only and coverage findings (other types handle them), and anything an open issue already covers.

**If the change claims to fix an issue** and the fix is incomplete, name that issue.
