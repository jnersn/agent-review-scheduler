# Docs and repo hygiene review

**Purpose:** keep the instructions that agents and people rely on true, and keep finished work out of the way.

**Scope:** agent instructions (CLAUDE.md, AGENTS.md and similar), README, plan, roadmap and docs files, plus top-level directories of experiments and tools.

**Look for:**
- **Instructions that no longer match the code:** symbols, files, commands, numbers or patterns that the instruction files name but that don't exist or don't match. Agents follow these files literally, so treat drift here as medium severity at least.
- **Stale plans and roadmaps:**
  - plan documents marked done, adopted or superseded but still presented as current;
  - checklists with shipped items still unchecked;
  - roadmaps that duplicate the issue tracker and have fallen behind it.
- **Finished experiments:** experiments, spikes and evidence archives that nothing references any more. Note any file that live code or scripts still import before proposing to archive it.
- **Broken links:** links between docs that point to moved or deleted files.
- **Ignore rules:** gaps in `.gitignore` where build output, local state or secrets could be committed.

**Each finding:** say the true fact, so the fix can be written straight from the review.

**Skip:** rewording docs that are still accurate; adding new documentation.
