# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

<!-- Entry format:
### ADR-NNN: <decision in one line>
- **Date**: YYYY-MM-DD
- **Status**: Accepted
- **Context**: <what forced the decision>
- **Decision**: <what was decided>
- **Consequences**: <what follows, including what it costs>
-->

### ADR-001: The timer owns no clock; `now` is always an argument
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: A focus timer tested by sleeping is slow and flaky, and a browser cannot be relied on to poll every second.
- **Decision**: `tempo/session.py` holds frozen states and pure transitions that take `now`. `settled()` advances past phases that elapsed between two polls and carries the overshoot into the new phase.
- **Consequences**: Every timer rule is unit-testable without sleeping, and a page that polls late lands on the same phase it would have reached by polling every second. The cost is that callers must thread a clock through; `TempoApp` holds the only one.

### ADR-002: All colour and type live in `web/theme.css`, the contract's single theme path
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: AIKit's style-drift lint only reports literals outside the theme paths a UI contract declares; with no theme path declared, the lint is off entirely.
- **Decision**: `web/theme.css` holds every colour, font and token, including the dark-mode block. `web/app.css` carries layout only, and `web/app.js` sets a `data-phase` attribute rather than any style. `.aikit/ui.json` declares `theme_paths: ["web/theme.css"]`.
- **Consequences**: A hardcoded colour or font anywhere else in `web/` is a mechanical finding rather than a matter of taste. The cost is that typography declarations cannot be written next to the layout they affect, which is why `.readout` is split across the two files.

### ADR-003: The snapshot proof is a parsed inventory, not a rendered screenshot
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: PRINCIPLE-015 R1 asks a web app to be loaded in a headless browser, but Tempo declares no dependencies and the standard library ships no browser engine.
- **Decision**: `tools/ui_inventory.py` parses `web/` and prints one line per identified element, named action, ARIA role, live region, script handler and theme token. `tools/dogfood.py` satisfies the backend-API criterion in full over a real socket and checks that the served page carries every control the script renders into.
- **Consequences**: A dropped control, action, role, live region or theme token is caught as a lost inventory line, and accessibility attributes are guarded alongside controls. A purely visual regression that keeps the inventory intact is not caught; that gap is deliberate and is the price of zero dependencies.

### ADR-004: A dropped connection is routine; a traceback fails the dogfood run
- **Date**: 2026-10-23
- **Status**: Accepted
- **Context**: A stray server left running answered a client that vanished mid-request and printed a full `ConnectionResetError` traceback, which happens whenever a browser tab closes during a poll. The dogfood runner captured the server's output but never inspected it, so PRINCIPLE-015 R6 was unenforced.
- **Decision**: `TempoServer.handle_error` stays silent for `ConnectionResetError`, `ConnectionAbortedError` and `BrokenPipeError` and reports anything else. The dogfood runner now resets a connection mid-request as one of its hostile inputs, keeps the server's output in its own sandbox file, and fails the run when that output contains a traceback.
- **Consequences**: A closing tab no longer looks like a fault, and a genuine unhandled error still surfaces and now fails a gate instead of scrolling past. The cost is that the runner must read the server log back, and its report is forced through ASCII so a localized OS message cannot break the console.

### ADR-005: Phase transition chimes use synthetic Web Audio tones; zero external assets
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Users need an audible signal when a focus or break phase completes without requiring visual focus on the tab. Bundling audio files increases repository size and introduces external asset dependencies.
- **Decision**: `web/app.js` synthesizes two-tone harmonic chimes using the browser's native `AudioContext` (sine oscillators with exponential gain decay). Sound can be toggled via `#sound-button`, preference persists in `localStorage`, and the audio context is unlocked upon user gesture.
- **Consequences**: Zero audio asset files or network calls are needed. Older browsers without Web Audio gracefully no-op.

### ADR-006: Runtime interval configuration updates the validated plan and persists alongside session state
- **Date**: 2026-10-24
- **Status**: Accepted
- **Context**: Changing focus or break durations previously required restarting Python with command-line flags. Users need to adjust interval durations directly from the UI.
- **Decision**: Added `configure` action to `TempoApp` accepting `focus_seconds`, `short_break_seconds`, `long_break_seconds`, and `cycle_length`. The updated plan is validated through `PhasePlan.validated()`, returned in status snapshots, and persisted as `"plan"` in `session.json` by `SessionStore`.
- **Consequences**: Users customize intervals live without restarting the server, and customizations persist across restarts. The schema remains backward-compatible with schema version 1.

## Licensing migration (agpl-final)

- New versions use the Aegean License 1.1 (AL-1.1); versions up to and including `agpl-final` remain under GNU AGPL-3.0.
- Rights holder: AegeanWorks; commercial use under ACL-1.0.
- Counsel review of the 1.1 texts remains pending.

## License notice cleanup (2026-10-26)

- The license-history notes were removed from README.md and COMMERCIAL.md: the project is offered only under the Aegean License 1.1 (AL-1.1), with commercial use under ACL-1.0.
