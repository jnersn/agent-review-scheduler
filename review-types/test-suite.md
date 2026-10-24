# Test suite review

**Purpose:** find tests that don't protect what they claim to, and risky code that no test covers.

**Scope:** the test suite, or the tests of an area named in the request.

**Look for:**
- **Tests of code production never calls:** tests that exercise a test-only or parallel implementation instead of the path production uses.
- **Tests that cannot fail:**
  - assertions on values the test itself set;
  - checks that also pass without the fix;
  - mocks that bypass the logic under test.
- **Timing instead of conditions:** fixed sleeps where waiting for a condition or an injected clock would work. Note this especially where it makes the suite slow or flaky.
- **Leaking shared state:** tests that leave state behind in global configuration, singletons, databases or files, or that depend on the order tests run in. Check the project's instructions for rules about running tests in parallel.
- **Untested risky code:** migrations, deletion, concurrency and cancellation, error paths, and other code where a bug loses data. Name the specific scenario a new test should cover.
- **Large duplicated setup** that should be one shared fixture.

**Skip:** coverage percentages for their own sake; tests that are merely long.
