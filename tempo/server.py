"""
The HTTP layer: a stdlib server that serves web/ and three JSON endpoints.

`TempoApp` is the whole backend contract — settle the stored session against the clock,
apply one named action, hand back the snapshot the UI renders. The request handler only
translates HTTP into those two calls, so the timer can be tested without a socket.

PRINCIPLE-009, PRINCIPLE-010, PRINCIPLE-011, PRINCIPLE-013.
"""

import json
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

from tempo.phases import PhasePlan
from tempo.session import advanced, paused, reset, settled, started
from tempo.status import snapshot
from tempo.store import SessionStore, StoreError

MAX_BODY_BYTES = 4096
READ_TIMEOUT_SECONDS = 10
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}
WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
# A browser that closes a tab, navigates away or is stopped mid-poll resets the
# connection. That is routine, not a fault, and must not print a traceback: PRINCIPLE-015
# R6 treats one on stderr as a failed run.
QUIET_ERRORS = (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)


@dataclass(frozen=True)
class StaticFiles:
    """Resolves a URL path to a file inside one directory, and never outside it."""

    root: Path

    def resolve(self, url_path: str) -> Optional[Path]:
        """The file a URL path names, or None when it escapes or does not exist."""
        relative = url_path.lstrip("/") or "index.html"
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None


class TempoApp:
    """One session's backend: settle it against the clock, act on it, report it."""

    ACTIONS = ("toggle", "skip", "reset", "configure")

    def __init__(self, store: SessionStore, plan: PhasePlan,
                 clock: Callable[[], float]):
        self.store = store
        saved_plan = self.store.load_plan()
        self.plan = saved_plan if saved_plan is not None else plan.validated()
        self.clock = clock

    def status(self) -> Dict[str, object]:
        """The current snapshot, persisting any phases that elapsed since the last call."""
        now = self.clock()
        stored = self.store.load()
        current = settled(stored, self.plan, now)
        if current != stored:
            self.store.save(current, self.plan)
        return snapshot(current, self.plan, now)

    def apply(self, action: str, params: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        """The snapshot after one named action; an unknown action raises ValueError."""
        if action not in self.ACTIONS:
            raise ValueError(f"unknown action {action!r}; expected one of "
                             f"{', '.join(self.ACTIONS)}")
        now = self.clock()
        current = settled(self.store.load(), self.plan, now)
        if action == "toggle":
            current = paused(current, now) if current.running else started(current, now)
        elif action == "skip":
            current = advanced(current, self.plan, now)
        elif action == "reset":
            current = reset(current)
        elif action == "configure":
            cfg = params or {}
            focus = int(cfg["focus_seconds"]) if "focus_seconds" in cfg and cfg["focus_seconds"] is not None else self.plan.focus_seconds
            short_b = int(cfg["short_break_seconds"]) if "short_break_seconds" in cfg and cfg["short_break_seconds"] is not None else self.plan.short_break_seconds
            long_b = int(cfg["long_break_seconds"]) if "long_break_seconds" in cfg and cfg["long_break_seconds"] is not None else self.plan.long_break_seconds
            cycle_l = int(cfg["cycle_length"]) if "cycle_length" in cfg and cfg["cycle_length"] is not None else self.plan.cycle_length
            from tempo.phases import PhasePlan
            self.plan = PhasePlan(focus, short_b, long_b, cycle_l).validated()
        self.store.save(current, self.plan)
        return snapshot(current, self.plan, now)


class TempoHandler(BaseHTTPRequestHandler):
    """Translates requests into `TempoApp` calls; the app owns every timer rule."""

    protocol_version = "HTTP/1.1"
    timeout = READ_TIMEOUT_SECONDS
    # Headers and body leave in one segment, so a localhost poll is not held up for a
    # delayed ACK (PRINCIPLE-010 R1).
    disable_nagle_algorithm = True
    wbufsize = 64 * 1024
    app: Optional[TempoApp] = None
    files: Optional[StaticFiles] = None

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        route = urlparse(self.path).path
        if route == "/api/status":
            self._guarded(lambda: (200, self.app.status()))
            return
        target = self.files.resolve(route)
        if target is None:
            self._json(404, {"error": "not found", "path": route})
            return
        body = target.read_bytes()
        self._respond(200, CONTENT_TYPES.get(target.suffix, "application/octet-stream"),
                      body, cache=route != "/" and not route.endswith(".html"))

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if urlparse(self.path).path != "/api/action":
            self._json(404, {"error": "not found", "path": self.path})
            return
        raw_length = self.headers.get("Content-Length") or "0"
        try:
            length = int(raw_length)
        except ValueError:
            self.close_connection = True
            self._json(400, {"error": "Content-Length must be an integer"})
            return
        if length < 0:
            self.close_connection = True
            self._json(400, {"error": "Content-Length must not be negative"})
            return
        if length > MAX_BODY_BYTES:
            self.close_connection = True
            self._json(413, {"error": f"body over {MAX_BODY_BYTES} bytes"})
            return
        raw = self.rfile.read(length) if length else b"{}"
        self._guarded(lambda: self._act(raw))

    def _act(self, raw: bytes) -> Tuple[int, Dict[str, object]]:
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("body must be a JSON object with an 'action' field")
        action = str(payload.get("action", ""))
        return 200, self.app.apply(action, payload)

    def _guarded(self, call: Callable[[], Tuple[int, Dict[str, object]]]) -> None:
        try:
            status, payload = call()
        except ValueError as error:
            self._json(400, {"error": str(error)})
        except StoreError as error:
            self._json(500, {"error": str(error), "why": error.why, "fix": error.fix})
        else:
            self._json(status, payload)

    def _json(self, status: int, payload: Dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._respond(status, "application/json; charset=utf-8", body, cache=False)

    def _respond(self, status: int, content_type: str, body: bytes, cache: bool) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=60" if cache else "no-store")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def log_message(self, format: str, *args) -> None:
        """Silent by default; `run.py` prints the one line a user needs."""


class TempoServer(HTTPServer):
    """An HTTP server that treats a dropped connection as routine, not as an error."""

    def handle_error(self, request, client_address) -> None:
        """Stay silent when the client simply went away; report anything else."""
        if isinstance(sys.exc_info()[1], QUIET_ERRORS):
            return
        super().handle_error(request, client_address)


def build_server(app: TempoApp, port: int, web: Path = WEB_ROOT,
                 host: str = "127.0.0.1") -> TempoServer:
    """An HTTP server bound to `host:port`, serving `web` and `app`."""
    handler = type("BoundTempoHandler", (TempoHandler,),
                   {"app": app, "files": StaticFiles(web)})
    return TempoServer((host, port), handler)
