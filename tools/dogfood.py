#!/usr/bin/env python3
"""
Tempo's own dogfood runner: use the product the way a user does, then attack it.

The golden path starts a real server on a free port, loads the page, drives the controls
over HTTP and reads the session back. The chaos track then feeds it malformed JSON, an
unknown action, an oversized body, concurrent requests and a corrupt session file. Every
process runs inside a context manager that kills its whole tree, everything written goes
under one temporary sandbox, and the tracked tree is fingerprinted before and after.

Usage: python tools/dogfood.py   (exit 0 pass, 1 fail, 2 cannot run)

PRINCIPLE-015.
"""

import contextlib
import hashlib
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / ".aikit" / "dogfood_last_run.log"
MAX_REPORT_LINES = 15
START_TIMEOUT = 20.0
REQUEST_TIMEOUT = 5.0
API_BUDGET_MS = 500.0
SUBPROCESS_TIMEOUT = 30
TRACEBACK_MARKER = "Traceback (most recent call last)"
STATUS_FIELDS = ("phase", "phase_index", "phase_seconds", "remaining_seconds",
                 "elapsed_seconds", "running", "completed_focus", "cycle_position",
                 "cycle_length")
CONTROLS = (b'id="run-button"', b'id="skip-button"', b'id="reset-button"',
            b'id="timer-display"', b'id="cycle-dots"')


class Report:
    """Collects step outcomes: the console sees a summary, the log sees everything."""

    def __init__(self) -> None:
        self.lines: List[str] = []
        self.failures: List[str] = []

    def step(self, ok: bool, label: str, detail: str = "") -> bool:
        """Record one step's outcome and hand back whether it passed."""
        mark = "PASS" if ok else "FAIL"
        self.lines.append(f"[{mark}] {label}" + (f" :: {detail}" if detail else ""))
        if not ok:
            self.failures.append(f"{label}: {detail}" if detail else label)
        return ok


def printable(text: str) -> str:
    """ASCII-safe text: a localized OS message must not break the report on a cp1254 console."""
    return str(text).encode("ascii", "replace").decode("ascii")


def terminate_process_tree(process: subprocess.Popen) -> None:
    """Kill a process and everything it started, on Windows and on POSIX alike."""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                           capture_output=True, timeout=SUBPROCESS_TIMEOUT)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=10)


@contextlib.contextmanager
def supervised(command: List[str], log):
    """Run a command with stdin closed (R3), killing its whole tree on the way out (R2)."""
    if os.name == "nt":
        creation = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        creation = {"start_new_session": True}
    options = dict(stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                   cwd=str(ROOT), **creation)
    # The server runs until this context manager exits; terminate_process_tree then kills
    # the whole tree and waits with a timeout on every path out (PRINCIPLE-015 R2).
    process = subprocess.Popen(command, **options)  # hygiene: allow RAII teardown
    try:
        yield process
    finally:
        terminate_process_tree(process)


def free_port() -> int:
    """A port the operating system says is free right now."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def fingerprint() -> str:
    """A digest of every tracked file, so a run that dirties the repository fails (R4)."""
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True,
                             timeout=SUBPROCESS_TIMEOUT)
    digest = hashlib.sha256()
    for name in sorted(part for part in listing.stdout.split(b"\0") if part):
        digest.update(name)
        path = ROOT / name.decode("utf-8")
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def get(base: str, path: str) -> Tuple[int, bytes, float]:
    """One GET, with the milliseconds it took."""
    started = time.monotonic()
    with urllib.request.urlopen(base + path, timeout=REQUEST_TIMEOUT) as response:
        body = response.read()
        status = response.status
    return status, body, (time.monotonic() - started) * 1000.0


def post(base: str, payload: object, raw: Optional[bytes] = None) -> Tuple[int, bytes]:
    """One action POST; an HTTP error is an answer here, not an exception."""
    data = raw if raw is not None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base + "/api/action", data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.read()


def wait_until_serving(base: str) -> bool:
    """True once the server answers, False if it never does within the start timeout."""
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        try:
            get(base, "/api/status")
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.05)
    return False


def golden_path(base: str, state: Path, report: Report) -> None:
    """Load the page, run the timer through a phase change, read the session back (R5)."""
    status, page, _ = get(base, "/")
    report.step(status == 200 and all(control in page for control in CONTROLS),
                "page serves every control the script renders into",
                f"HTTP {status}, {len(page)} bytes")

    code, body, elapsed = get(base, "/api/status")
    first = json.loads(body)
    report.step(code == 200 and all(field in first for field in STATUS_FIELDS),
                "GET /api/status answers the declared schema", f"HTTP {code}")
    report.step(elapsed < API_BUDGET_MS, "status answers inside its 500ms budget",
                f"{elapsed:.0f}ms")

    code, body = post(base, {"action": "toggle"})
    report.step(code == 200 and json.loads(body)["running"] is True,
                "toggle starts the timer", f"HTTP {code}")

    time.sleep(1.1)
    counted = json.loads(get(base, "/api/status")[1])
    report.step(counted["remaining_seconds"] < first["remaining_seconds"],
                "the clock advances while running",
                f"{first['remaining_seconds']}s -> {counted['remaining_seconds']}s")

    time.sleep(2.2)
    rolled = json.loads(get(base, "/api/status")[1])
    report.step(rolled["phase"] == "short-break" and rolled["completed_focus"] == 1,
                "a finished focus phase rolls into the break and is counted",
                f"{rolled['phase']}, {rolled['completed_focus']} done")
    report.step(state.is_file()
                and json.loads(state.read_text(encoding="utf-8"))["schema"] == 1,
                "the session is persisted with its schema version")

    code, body = post(base, {"action": "reset"})
    report.step(code == 200 and json.loads(body)["completed_focus"] == 0,
                "reset clears the session", f"HTTP {code}")


def drop_mid_request(base: str, port: int, report: Report) -> None:
    """Reset a connection halfway through a request, as a closing browser tab does."""
    probe = socket.create_connection(("127.0.0.1", port), timeout=REQUEST_TIMEOUT)
    try:
        probe.sendall(b"GET /api/status HTTP/1.1\r\nHost: tempo\r\n")
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    finally:
        probe.close()
    code, _, _ = get(base, "/api/status")
    report.step(code == 200, "a dropped connection leaves the server serving",
                f"HTTP {code}")


def chaos(base: str, port: int, state: Path, report: Report) -> None:
    """Hostile inputs: malformed JSON, bad values, a flood and a corrupt session (R5)."""
    drop_mid_request(base, port, report)

    code, body = post(base, None, raw=b"{not json at all")
    report.step(code == 400 and b"error" in body, "malformed JSON answers 400", f"HTTP {code}")

    code, body = post(base, {"action": "self-destruct"})
    report.step(code == 400 and b"unknown action" in body, "unknown action answers 400",
                f"HTTP {code}")

    padded = b'{"action":"toggle","pad":"' + b"x" * 8192 + b'"}'
    code, _ = post(base, None, raw=padded)
    report.step(code == 413, "an oversized body answers 413", f"HTTP {code}")

    code, _ = post(base, [1, 2, 3])
    report.step(code == 400, "a JSON array body answers 400", f"HTTP {code}")

    results: Dict[int, int] = {}
    lock = threading.Lock()

    def hammer() -> None:
        try:
            status = get(base, "/api/status")[0]
        except (urllib.error.URLError, OSError):
            status = 0
        with lock:
            results[status] = results.get(status, 0) + 1

    threads = [threading.Thread(target=hammer) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(REQUEST_TIMEOUT * 2)
    report.step(results.get(200) == len(threads), "12 concurrent polls all answer 200",
                str(results))

    state.write_text("{ truncated", encoding="utf-8")
    code, body, _ = get(base, "/api/status")
    report.step(code == 200 and json.loads(body)["phase"] == "focus",
                "a corrupt session file is quarantined and the UI still renders",
                f"HTTP {code}")
    report.step(state.with_suffix(state.suffix + ".corrupt").is_file(),
                "the unreadable session is kept for inspection")


def surface_proof(report: Report, log) -> None:
    """The UI inventory proof runs and reports its surface, as the UI guard expects."""
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "ui_inventory.py")],
                          capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT,
                          cwd=str(ROOT))
    log.write(done.stdout + done.stderr)
    entries = [line for line in done.stdout.splitlines() if line.strip()]
    report.step(done.returncode == 0 and len(entries) >= 20,
                "the UI inventory proof reports its surface", f"{len(entries)} entries")


def main() -> int:
    """Run both tracks in one sandbox and print at most 15 lines (R6, R7)."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = Report()
    before = fingerprint()
    with tempfile.TemporaryDirectory(prefix="tempo-dogfood-") as box:
        with open(LOG_PATH, "w", encoding="utf-8") as log:
            state = Path(box) / "session.json"
            server_log = Path(box) / "server.log"
            port = free_port()
            base = f"http://127.0.0.1:{port}"
            command = [sys.executable, str(ROOT / "run.py"), "--port", str(port),
                       "--state", str(state), "--focus", "0.05"]
            alive = False
            with open(server_log, "w", encoding="utf-8") as sink:
                with supervised(command, sink) as process:
                    if wait_until_serving(base):
                        report.step(True, "the server starts and answers", base)
                        golden_path(base, state, report)
                        chaos(base, port, state, report)
                    else:
                        report.step(False, "the server starts and answers",
                                    f"no answer within {START_TIMEOUT:.0f}s")
                    alive = process.poll() is None
            report.step(alive, "the server survived every hostile input")

            # R6: a traceback on the server's stderr fails the run even when every
            # request answered correctly, so the log is evidence, not decoration.
            printed = server_log.read_text(encoding="utf-8", errors="replace")
            log.write("--- server output ---\n" + printed + "--- steps ---\n")
            culprit = next((line.strip() for line in printed.splitlines()
                            if line.strip().endswith("Error")
                            or ": [WinError" in line), "")
            report.step(TRACEBACK_MARKER not in printed,
                        "the server printed no traceback", culprit[:90])

            surface_proof(report, log)
            log.write("\n".join(report.lines) + "\n")

    report.step(fingerprint() == before, "the run left the tracked tree untouched")
    passed = len(report.lines) - len(report.failures)
    print(f"TEMPO DOGFOOD (PRINCIPLE-015): {passed}/{len(report.lines)} steps passed")
    for failure in report.failures[:MAX_REPORT_LINES - 4]:
        print(f"  [FAIL] {printable(failure)}")
    print(f"  full log: {LOG_PATH.relative_to(ROOT).as_posix()}")
    if report.failures:
        print("Why: the product must work and hold up under hostile input before it ships.")
        print("Fix: read the log, fix the failing step, then rerun this command.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
