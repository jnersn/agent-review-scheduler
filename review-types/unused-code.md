# Unused code sweep

**Purpose:** find code that can be deleted, and code that only runs in configurations no production build or deployment uses.

**Scope:** the whole project unless the request narrows it. If the request includes a report from a dead-code tool, start from it and verify each entry by hand.

**Look for:**
- declarations unused anywhere: types, functions, methods, properties, enum cases, constants and helpers;
- declarations used only by tests, where the tests exercise a parallel path that production never calls. Point the tests at the real path;
- code that only runs behind a build configuration, feature flag, environment variable or setting that no production build or deployment sets;
- constants and settings that never change in production, and the branches that depend on them;
- registrations in a dependency container or router that nothing uses, and test helpers or fixtures that no test uses.

**Before reporting**, rule out false positives:
- interface and protocol requirements, callbacks and event handlers;
- code reached by reflection, decorators, annotations or dynamic dispatch;
- fields used by serialization, ORMs or templates;
- framework entry points such as routes, CLI commands, lifecycle hooks, previews and plugin registrations;
- string-based lookups and configuration-driven wiring;
- the public API of a library, which its users may call;
- overloaded names.

Keep deliberate test hooks that are documented as such. Check the roadmap and open issues: code waiting for planned work is not dead (see common.md).

**Output:** group the findings as "unused anywhere", "used only by tests" and "only behind a flag or configuration". Give the number of raw candidates and the number you verified.
