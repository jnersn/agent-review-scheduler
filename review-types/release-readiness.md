# Build and release readiness review

**Purpose:** catch build, configuration and packaging problems before a release.

**Scope:** build and project configuration, CI workflows, manifests, permissions, dependency files, packaging and deployment files, and anything the release embeds. This is not a code bug hunt.

**Look for:**
- **Build configurations:** configurations, targets or CI jobs left over from experiments; settings that differ between debug and release builds without a reason; debug-only code or flags that can reach production.
- **Version numbers:** the version and build numbers, against the project's versioning rules, and consistency between the places that state them.
- **Platform manifests and permissions:** for example app entitlements, Info.plist usage descriptions and privacy manifests, Android manifests, container images and deployment manifests. Look for permissions broader than the code needs, debug settings in release, and missing or wrong user-facing permission texts.
- **Dependencies:**
  - unpinned versions or branches;
  - lockfiles out of sync with the manifest;
  - pins that are stale or diverge from what the docs say;
  - packages nothing uses.
- **Embedded content:** assets, models and resources missing from the package, unsigned, or referenced by code but not included.
- **Compiler and linters:** warnings, or disabled checks, introduced since the last release.

**Skip:** anything a manual QA pass covers, and store-listing or marketing copy.
