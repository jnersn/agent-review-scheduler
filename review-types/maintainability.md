# Maintainability review

**Purpose:** find over-engineering, duplication and drift from conventions, so the code can be simplified. This is not a bug hunt; report a bug you come across only if it is clear-cut.

**Scope:** one layer or area named in the request, or the whole project.

**Look for:**
- **Needless abstraction:** interfaces or abstractions with a single implementation and no test seam; layers that only forward calls; settings and configuration knobs that are never varied.
- **Copied state:** state copied from another object into a second stored copy when it should be read through. The copies lag behind and cause extra work or stale UI.
- **Inconsistent patterns:** for example, two dependency-injection styles in one module, or a service looked up in more than one way.
- **Duplicated logic:** logic repeated in 3 or more places, or in 2 places that have already drifted apart. Give every location and propose one shared helper.
- **Lint-driven splits:** files split only to satisfy length rules where the split weakens encapsulation, such as private members becoming module-visible. Prefer shrinking the type over splitting it.
- **Misplaced logic:** business logic in UI code or request handlers that belongs in a model or service, or feature logic in shared utilities.

**For each finding**, say whether it is worth doing now. A large refactor with a small payoff is low severity.

**Skip:** renames and formatting; rewrites with no concrete payoff; "consider using X" with no current problem. Also skip anything that would break a documented project convention, such as its state-management or dependency-injection approach.
