# UI consistency and accessibility review

**Purpose:** find places where the same action behaves differently depending on where the user performs it, and controls that can't be reached with the keyboard or a screen reader.

**Scope:** the screens or views named in the request, or a cross-cutting action (for example: delete, share, context menus, copy) checked across every view that offers it.

**Look for:**
- **Actions that differ between views:** menus, commands, shortcuts and toolbar items that differ between views showing the same items (for example: list, grid, table and detail views). Look for missing entries, different wording and different enabled states.
- **The same action in several places:** list each place that implements it separately, and any that have drifted.
- **Keyboard:** controls you can't reach with the keyboard, focus lost after dialogs, focus traps, and shortcuts that clash between contexts.
- **Screen readers:** missing or stale labels, values and actions; decorative images that are not hidden; custom controls with no role or accessibility traits.
- **Inconsistent states:** empty, loading and error states that differ between equivalent views.

**Skip:** visual-design preferences, and the layout of a single view in isolation.
