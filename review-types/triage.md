# Triage of review findings

Reviewers found the findings in `.review/candidates.json`. Each one that you mark `file` becomes its own issue in the tracker tonight, without anyone checking it first. Your job is to keep that tracker worth reading: file what a maintainer would want to fix, and leave the rest in the report, where the maintainer can still find it.

You work read-only. Decide each finding on its own merits; the order and the number of findings don't matter (a separate limit caps how many issues are filed).

## For each finding
1. **Check that it is real.** Read the code it cites at this checkout and follow the scenario. If the code doesn't do what the finding says, or the scenario needs a state the app can't reach, it is `skip`.
2. **Check that it is new.** Compare it with `.review/known-issues.md`, reading an issue's title closely, and the cited code if needed.
   - An open issue already covers it: `duplicate`, with that issue's number.
   - A closed issue covers it and the fix is in this checkout: `duplicate`.
   - A closed issue's fix is missing or has regressed: that's new; `file`, and say so in the reason.
   - Two findings here share a root cause: `file` the clearer one and `skip` the other, with "same as N.N".
3. **Decide whether it is worth an issue.** `file` it when fixing it has a clear payoff:
   - a bug a user can hit (a wrong result, lost or wrong data, a crash or hang, a privacy or security problem);
   - a missing test or a flaky test hiding a real risk;
   - debt or dead code with a concrete, nameable cost now, such as two copies of state that disagree or a path no one can safely change.

   `skip` it when it is speculative, cosmetic, style or naming, intended and documented behaviour, a refactor with no concrete cost, advice rather than a defect, or an edge case so rare and minor that no one would schedule it.
4. **When unsure, skip.** The finding stays in the report; a wrongly filed issue costs the maintainer more.

## Output
A few lines of notes if you need them, then, last, one fenced `json` block with a decision for every finding:

```json
{"decisions": [
  {"id": "1.1", "decision": "file", "reason": "Confirmed: verifyModel's damaged-import branch never clears the error; a user sees the wrong reason."},
  {"id": "1.2", "decision": "duplicate", "issue": 573, "reason": "#573 covers the same reconnect race."},
  {"id": "2.1", "decision": "skip", "reason": "Naming only; no behaviour changes."}
]}
```

`decision` is `file`, `duplicate` or `skip`. `issue` is a number, only for `duplicate` when there is one. `reason` is one sentence; for `file` it says what you confirmed.
