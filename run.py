#!/usr/bin/env python3
"""
Start Tempo and print the one URL a user needs.

Zero dependencies beyond the standard library, no environment variables and no prompts:
pick a port, open the page. The session file is created on first write, under the state
directory given by `--state`.

PRINCIPLE-011.
"""

import argparse
import sys
import time
from pathlib import Path

from tempo.phases import PhasePlan
from tempo.server import WEB_ROOT, TempoApp, build_server
from tempo.store import SessionStore, StoreError

DEFAULT_PORT = 8765
DEFAULT_STATE = Path(__file__).resolve().parent / "state" / "session.json"


def parse_args(argv):
    """The command line: port, state file and the three phase lengths in minutes."""
    parser = argparse.ArgumentParser(
        prog="python run.py", description="Run Tempo's focus timer on this machine.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE,
                        help="session state file (default: state/session.json)")
    parser.add_argument("--focus", type=float, default=25.0, help="focus minutes")
    parser.add_argument("--short-break", type=float, default=5.0, help="short break minutes")
    parser.add_argument("--long-break", type=float, default=15.0, help="long break minutes")
    parser.add_argument("--cycle", type=int, default=4,
                        help="focus phases before a long break")
    return parser.parse_args(argv)


def build_plan(args) -> PhasePlan:
    """The phase plan the flags describe, validated before the socket is opened."""
    return PhasePlan(
        focus_seconds=int(round(args.focus * 60)),
        short_break_seconds=int(round(args.short_break * 60)),
        long_break_seconds=int(round(args.long_break * 60)),
        cycle_length=args.cycle,
    ).validated()


def main(argv=None) -> int:
    """Serve until interrupted; 0 on a clean stop, 1 on a start failure, 2 on bad flags."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        plan = build_plan(args)
    except ValueError as error:
        print(f"invalid phase plan: {error}", file=sys.stderr)
        print("Why: each phase must last between 1 second and 24 hours, and a cycle "
              "must hold at least one focus phase.", file=sys.stderr)
        print("Fix: pass positive --focus, --short-break and --long-break minutes and "
              "a --cycle of 1 or more.", file=sys.stderr)
        return 2
    app = TempoApp(SessionStore(args.state), plan, time.monotonic)
    try:
        server = build_server(app, args.port, WEB_ROOT)
    except OSError as error:
        print(f"could not listen on port {args.port}: {error}", file=sys.stderr)
        print("Why: another process already holds that port.", file=sys.stderr)
        print("Fix: stop it, or start Tempo with --port <other>.", file=sys.stderr)
        return 1
    host, port = server.server_address[0], server.server_address[1]
    print(f"Tempo is running at http://{host}:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTempo stopped.")
    except StoreError as error:
        print(f"{error}\nWhy: {error.why}\nFix: {error.fix}", file=sys.stderr)
        return 1
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
