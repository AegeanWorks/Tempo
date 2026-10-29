# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `16`
- **Total Classes**: `20`
- **Total Top-Level Functions**: `31`
- **Total Class Methods**: `82`
- **Total Source Lines**: `1614`

---

## 📦 Modules & Exported Symbols

### [`run.py`](run.py)
> *Start Tempo and print the one URL a user needs.*

**Size**: `86` lines (`3468` bytes)

**Functions:**
- `def parse_args(argv)` - *The command line: port, state file and the three phase lengths in minutes.*
- `def build_plan(args)` - *The phase plan the flags describe, validated before the socket is opened.*
- `def main(argv)` - *Serve until interrupted; 0 on a clean stop, 1 on a start failure, 2 on bad flags.*

---

### [`tempo/__init__.py`](tempo/__init__.py)
> *Tempo: a zero-dependency focus timer with a themed browser UI.*

**Size**: `3` lines (`121` bytes)

---

### [`tempo/phases.py`](tempo/phases.py)
> *The phase plan: which phase follows which, and how long each one runs.*

**Size**: `57` lines (`1972` bytes)

**Classes:**
- `class Phase` - *One phase of a session: its kind and its full duration in seconds.*
- `class PhasePlan` - *Durations and cycle length for a session's phase sequence.*
  - Method `.validated()` - *The same plan, or a ValueError naming the field that is out of range.*
  - Method `.phase_at(index)` - *The phase at a zero-based index: even indexes focus, odd ones break.*

---

### [`tempo/server.py`](tempo/server.py)
> *The HTTP layer: a stdlib server that serves web/ and three JSON endpoints.*

**Size**: `200` lines (`8688` bytes)

**Classes:**
- `class StaticFiles` - *Resolves a URL path to a file inside one directory, and never outside it.*
  - Method `.resolve(url_path)` - *The file a URL path names, or None when it escapes or does not exist.*
- `class TempoApp` - *One session's backend: settle it against the clock, act on it, report it.*
  - Method `.__init__(store, plan, clock)`
  - Method `.status()` - *The current snapshot, persisting any phases that elapsed since the last call.*
  - Method `.apply(action, params)` - *The snapshot after one named action; an unknown action raises ValueError.*
- `class TempoHandler` - *Translates requests into `TempoApp` calls; the app owns every timer rule.*
  - Method `.do_GET()`
  - Method `.do_POST()`
  - Method `._act(raw)`
  - Method `._guarded(call)`
  - Method `._json(status, payload)`
  - Method `._respond(status, content_type, body, cache)`
  - Method `.log_message(format, *args)` - *Silent by default; `run.py` prints the one line a user needs.*
- `class TempoServer` - *An HTTP server that treats a dropped connection as routine, not as an error.*
  - Method `.handle_error(request, client_address)` - *Stay silent when the client simply went away; report anything else.*

**Functions:**
- `def build_server(app, port, web, host)` - *An HTTP server bound to `host:port`, serving `web` and `app`.*

---

### [`tempo/session.py`](tempo/session.py)
> *Session state and its transitions.*

**Size**: `104` lines (`3889` bytes)

**Classes:**
- `class SessionState` - *Where a session stands: its phase, its run clock and its finished focus count.*
  - Method `.initial()` - *A fresh, paused session at the first focus phase.*

**Functions:**
- `def elapsed_seconds(state, now)` - *Seconds spent in the current phase, including the run in progress.*
- `def remaining_seconds(state, plan, now)` - *Seconds left in the current phase, never below zero.*
- `def started(state, now)` - *The session running from `now`; starting a running session changes nothing.*
- `def paused(state, now)` - *The session paused, banking the elapsed run; pausing a paused one is a no-op.*
- `def advanced(state, plan, now)` - *The next phase, from a standing start, counting a finished focus phase.*
- `def settled(state, plan, now)` - *The state with every phase that ran out before `now` advanced past.*
- `def reset(state)` - *A fresh session, keeping nothing from the old one.*

---

### [`tempo/status.py`](tempo/status.py)
> *The read model the UI renders.*

**Size**: `51` lines (`2067` bytes)

**Functions:**
- `def snapshot(state, plan, now)` - *A settled session as the flat payload `GET /api/status` returns.*

---

### [`tempo/store.py`](tempo/store.py)
> *Crash-safe persistence for one session.*

**Size**: `144` lines (`5945` bytes)

**Classes:**
- `class StoreError` - *A state file this build must not touch: the caller reports why and the fix.*
  - Method `.__init__(message, why, fix)`
- `class SessionStore` - *Reads and writes one session file, atomically and without ever losing the old one.*
  - Method `.__init__(path)`
  - Method `.load()` - *The stored session, or a fresh one when no readable file exists.*
  - Method `.load_plan()` - *The stored phase plan, or None if not saved or unreadable.*
  - Method `.save(state, plan)` - *The session on disk, replaced atomically; the directory is created if missing.*
  - Method `._replace(temporary)`
  - Method `._quarantine()`

**Functions:**
- `def _decode(payload)`

---

### [`tests/__init__.py`](tests/__init__.py)
> *Tempo's test suites: unit tiers under 10ms, integration tiers under 350ms.*

**Size**: `1` lines (`81` bytes)

---

### [`tests/test_app.py`](tests/test_app.py)
> *Unit tests for the backend contract: status, actions and static path safety.*

**Size**: `120` lines (`4796` bytes)

**Classes:**
- `class FakeClock` - *A clock the test moves by hand, so no test ever sleeps (PRINCIPLE-014 R5).*
  - Method `.__init__()`
  - Method `.__call__()`
- `class TempoAppTest`
  - Method `.setUp()`
  - Method `.test_first_status_is_a_paused_focus_phase()`
  - Method `.test_toggle_starts_then_pauses_and_the_clock_only_runs_while_started()`
  - Method `.test_status_persists_phases_that_elapsed_between_polls()`
  - Method `.test_skip_moves_on_and_reset_starts_over()`
  - Method `.test_configure_action_updates_plan_and_persists_it()`
  - Method `.test_configure_with_invalid_values_raises_value_error()`
  - Method `.test_unknown_action_is_refused_and_leaves_the_session_alone()`
  - Method `.test_an_invalid_plan_is_refused_when_the_app_is_built()`
- `class StaticFilesTest`
  - Method `.setUp()`
  - Method `.test_root_serves_the_index()`
  - Method `.test_paths_outside_the_web_root_are_refused()`

---

### [`tests/test_http.py`](tests/test_http.py)
> *Integration tests over a real socket: the JSON endpoints and the served page.*

**Size**: `154` lines (`6712` bytes)

**Classes:**
- `class HttpTest`
  - Method `.setUp()`
  - Method `.get(path)`
  - Method `.post(path, payload)`
  - Method `.test_status_and_actions_round_trip_over_http()`
  - Method `.test_the_page_and_its_assets_are_served_with_their_types()`
  - Method `.test_configure_action_over_http()`
  - Method `.test_an_unknown_action_answers_400_with_a_reason()`
  - Method `.test_a_client_that_drops_mid_request_is_not_an_error()`
  - Method `.test_unknown_paths_answer_404()`
  - Method `.test_negative_content_length_is_refused_without_reading()`
  - Method `.test_non_numeric_content_length_is_refused()`
  - Method `.test_oversized_body_is_refused_and_the_connection_closes()`
  - Method `.raw_post(content_length, body)`

---

### [`tests/test_session.py`](tests/test_session.py)
> *Unit tests for the phase plan, session transitions and the status read model.*

**Size**: `124` lines (`5754` bytes)

**Classes:**
- `class PhasePlanTest`
  - Method `.test_sequence_alternates_and_lengthens_every_cycle()`
  - Method `.test_negative_index_is_refused()`
  - Method `.test_validated_names_the_bad_field()`
- `class SessionTransitionTest`
  - Method `.test_pause_banks_elapsed_and_resume_continues()`
  - Method `.test_repeated_start_and_pause_are_no_ops()`
  - Method `.test_advance_counts_only_finished_focus_phases()`
  - Method `.test_paused_session_never_settles_forward()`
  - Method `.test_settle_carries_overshoot_into_the_new_phase()`
  - Method `.test_reset_returns_a_fresh_session()`
  - Method `.test_advanced_records_completed_focus_in_history()`
- `class SnapshotTest`
  - Method `.test_snapshot_reports_whole_seconds_and_cycle_position()`
  - Method `.test_snapshot_includes_plan_durations_and_analytics()`
  - Method `.test_snapshot_keeps_recorded_duration_when_the_plan_changes()`
  - Method `.test_legacy_history_without_a_duration_uses_the_current_plan()`
  - Method `.test_remaining_never_goes_negative()`

---

### [`tests/test_store.py`](tests/test_store.py)
> *Unit tests for atomic session persistence, schema refusal and quarantine.*

**Size**: `108` lines (`5044` bytes)

**Classes:**
- `class SessionStoreTest`
  - Method `.setUp()`
  - Method `.test_missing_file_reads_as_a_fresh_session()`
  - Method `.test_round_trip_preserves_every_field()`
  - Method `.test_legacy_timestamp_only_history_is_migrated()`
  - Method `.test_wrong_typed_session_fields_are_quarantined()`
  - Method `.test_overflowing_number_is_quarantined()`
  - Method `.test_plan_persistence_and_reload()`
  - Method `.test_save_leaves_no_temporary_files_behind()`
  - Method `.test_unknown_schema_is_refused_without_touching_the_file()`
  - Method `.test_corrupt_file_is_quarantined_and_replaced_by_a_fresh_session()`
  - Method `.test_a_blocked_quarantine_is_reported_instead_of_swallowed()`
  - Method `.test_missing_fields_count_as_corrupt()`

---

### [`tests/test_ui_inventory.py`](tests/test_ui_inventory.py)
> *Unit tests for the UI inventory parser: the handler list is the guard's evidence.*

**Size**: `31` lines (`929` bytes)

**Classes:**
- `class HandlerEntriesTest`
  - Method `.setUp()`
  - Method `.test_quoted_and_hyphenated_keys_are_included()`

---

### [`tools/__init__.py`](tools/__init__.py)
> *Developer tools that are not part of the Tempo runtime.*

**Size**: `1` lines (`62` bytes)

---

### [`tools/dogfood.py`](tools/dogfood.py)
> *Tempo's own dogfood runner: use the product the way a user does, then attack it.*

**Size**: `328` lines (`14262` bytes)

**Classes:**
- `class Report` - *Collects step outcomes: the console sees a summary, the log sees everything.*
  - Method `.__init__()`
  - Method `.step(ok, label, detail)` - *Record one step's outcome and hand back whether it passed.*

**Functions:**
- `def printable(text)` - *ASCII-safe text: a localized OS message must not break the report on a cp1254 console.*
- `def terminate_process_tree(process)` - *Kill a process and everything it started, on Windows and on POSIX alike.*
- `def supervised(command, log)` - *Run a command with stdin closed (R3), killing its whole tree on the way out (R2).*
- `def free_port()` - *A port the operating system says is free right now.*
- `def fingerprint()` - *A digest of every tracked file, so a run that dirties the repository fails (R4).*
- `def get(base, path)` - *One GET, with the milliseconds it took.*
- `def post(base, payload, raw)` - *One action POST; an HTTP error is an answer here, not an exception.*
- `def wait_until_serving(base)` - *True once the server answers, False if it never does within the start timeout.*
- `def golden_path(base, state, report)` - *Load the page, run the timer through a phase change, read the session back (R5).*
- `def drop_mid_request(base, port, report)` - *Reset a connection halfway through a request, as a closing browser tab does.*
- `def chaos(base, port, state, report)` - *Hostile inputs: malformed JSON, bad values, a flood and a corrupt session (R5).*
- `def surface_proof(report, log)` - *The UI inventory proof runs and reports its surface, as the UI guard expects.*
- `def main()` - *Run both tracks in one sandbox and print at most 15 lines (R6, R7).*

---

### [`tools/ui_inventory.py`](tools/ui_inventory.py)
> *Print Tempo's UI inventory, one entry per line.*

**Size**: `102` lines (`3757` bytes)

**Classes:**
- `class SurfaceParser` - *Collects the identified elements, named actions and live regions of one page.*
  - Method `.__init__()`
  - Method `.handle_starttag(tag, attrs)`

**Functions:**
- `def html_entries(path)` - *Identified elements, actions, roles and live regions declared in a page.*
- `def handler_entries(path)` - *Action names the browser script is willing to dispatch.*
- `def token_entries(path)` - *Theme custom properties the stylesheet declares.*
- `def inventory(web)` - *Every inventory entry of a web directory, sorted and deduplicated.*
- `def main(argv)` - *Write the inventory to stdout; exit 1 when the surface has no entries at all.*

---
