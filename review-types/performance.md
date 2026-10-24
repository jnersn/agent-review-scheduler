# Performance review

**Purpose:** find work the code does that it doesn't need to, or does in the wrong place.

**Scope:** an area or layer named in the request, or the paths that run per item, per request, per keystroke or per tick of a background job.

**Look for:**
- **Work on a latency-critical path that grows with the data:** loops over every item, sorting or filtering large collections, synchronous I/O or decoding on a UI thread or in a request handler.
- **Unneeded re-rendering or recomputation:**
  - UI components that observe or subscribe to state they never read;
  - an object that forwards every change from another object, so its observers update on progress ticks;
  - copies of state that cause a second update.
- **Repeated queries:** database queries, network calls or file-system calls inside loops (N+1), and refetching what is already in memory.
- **Unbounded resources:** caches with no limit, queues that grow without bound, and work that is not cancelled when the user navigates away or a request is abandoned.
- **Duplicated work:** the same work done twice for one event, or a debounce that doesn't coalesce.

**For each finding**, give the scale at which it hurts (for example, "10k items", "every keystroke", "every request"), and say how to measure it: a test, a benchmark or a profiler.

**Skip:** micro-optimisations with no path that scales, and speculation without a trigger you have traced.
