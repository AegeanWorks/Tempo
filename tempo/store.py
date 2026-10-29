"""
Crash-safe persistence for one session.

The state file is written to a temporary sibling, flushed, fsynced and moved into place,
so a power loss leaves either the old file or the new one and never a half-written mix.
A file whose schema version this build does not know is refused untouched; a corrupt file
is quarantined and replaced by a fresh session, so the UI always has something to render.

PRINCIPLE-011, PRINCIPLE-013.
"""

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Tuple

from tempo.session import SessionState

SCHEMA = 1
REPLACE_ATTEMPTS = 5
FIELDS = ("phase_index", "running", "started_at", "spent_seconds", "completed_focus")


class StoreError(RuntimeError):
    """A state file this build must not touch: the caller reports why and the fix."""

    def __init__(self, message: str, why: str, fix: str):
        super().__init__(message)
        self.why = why
        self.fix = fix


def _decode(payload: object) -> SessionState:
    if not isinstance(payload, dict):
        raise ValueError("state file is not a JSON object")
    version = payload.get("schema")
    if version != SCHEMA:
        raise StoreError(
            f"session file has schema {version!r}, not {SCHEMA}.",
            "a newer Tempo wrote this session and its fields may mean something else.",
            "upgrade Tempo, or move the file aside to start a fresh session.")
    session = payload.get("session")
    if not isinstance(session, dict) or any(field not in session for field in FIELDS):
        raise ValueError("state file is missing session fields")
    history_raw = session.get("history", ())
    history: List[Tuple[float, Optional[int]]] = []
    if isinstance(history_raw, (list, tuple)):
        for entry in history_raw:
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                seconds = None if entry[1] is None else int(entry[1])
                history.append((float(entry[0]), seconds))
            else:
                history.append((float(entry), None))
    return SessionState(
        phase_index=int(session["phase_index"]),
        running=bool(session["running"]),
        started_at=None if session["started_at"] is None else float(session["started_at"]),
        spent_seconds=float(session["spent_seconds"]),
        completed_focus=int(session["completed_focus"]),
        history=tuple(history),
    )


class SessionStore:
    """Reads and writes one session file, atomically and without ever losing the old one."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.quarantine = self.path.with_suffix(self.path.suffix + ".corrupt")

    def load(self) -> SessionState:
        """The stored session, or a fresh one when no readable file exists."""
        if not self.path.exists():
            return SessionState.initial()
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                return _decode(json.load(handle))
        except StoreError:
            raise
        except (OSError, ValueError, TypeError, OverflowError):
            self._quarantine()
            return SessionState.initial()

    def load_plan(self) -> Optional[object]:
        """The stored phase plan, or None if not saved or unreadable."""
        if not self.path.exists():
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict) and isinstance(payload.get("plan"), dict):
                from tempo.phases import PhasePlan
                plan_dict = payload["plan"]
                fields = ("focus_seconds", "short_break_seconds", "long_break_seconds", "cycle_length")
                kwargs = {k: int(plan_dict[k]) for k in fields if k in plan_dict}
                return PhasePlan(**kwargs).validated()
        except Exception:
            return None
        return None

    def save(self, state: SessionState, plan: Optional[object] = None) -> None:
        """The session on disk, replaced atomically; the directory is created if missing."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": SCHEMA, "session": asdict(state)}
        if plan is not None:
            payload["plan"] = asdict(plan)
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(self.path.parent),
            prefix=self.path.name + ".", suffix=".tmp", delete=False)
        temporary = Path(handle.name)
        try:
            with handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            self._replace(temporary)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _replace(self, temporary: Path) -> None:
        last: Optional[OSError] = None
        for _ in range(REPLACE_ATTEMPTS):
            try:
                os.replace(str(temporary), str(self.path))
                return
            except OSError as error:
                last = error
        raise StoreError(
            f"could not replace {self.path.name} after {REPLACE_ATTEMPTS} attempts ({last}).",
            "another process is holding the session file open.",
            "close other Tempo servers, then retry.")

    def _quarantine(self) -> None:
        try:
            os.replace(str(self.path), str(self.quarantine))
        except OSError as error:
            raise StoreError(
                f"could not move the unreadable session file aside ({error}).",
                "the session file cannot be parsed and cannot be renamed, so starting a "
                "fresh session would overwrite whatever it still holds.",
                f"move or delete {self.path} by hand, then start Tempo again.") from error
