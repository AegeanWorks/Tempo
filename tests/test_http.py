"""Integration tests over a real socket: the JSON endpoints and the served page."""

import contextlib
import io
import json
import socket
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from tempo.phases import PhasePlan
from tempo.server import TempoApp, build_server
from tempo.store import SessionStore

WEB = Path(__file__).resolve().parent.parent / "web"
TIMEOUT = 5
# `shutdown` waits for the serving loop to notice; the default 0.5s poll interval would
# cost every test half a second of teardown (PRINCIPLE-010 R6).
POLL_INTERVAL = 0.005


class HttpTest(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.moment = [500.0]
        app = TempoApp(SessionStore(Path(directory.name) / "session.json"),
                       PhasePlan(focus_seconds=10, short_break_seconds=5, cycle_length=2),
                       lambda: self.moment[0])
        self.server = build_server(app, 0, WEB)
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(
            target=self.server.serve_forever, args=(POLL_INTERVAL,), daemon=True)
        thread.start()
        self.addCleanup(thread.join, TIMEOUT)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=TIMEOUT) as response:
            return response.status, response.headers, response.read()

    def post(self, path, payload):
        request = urllib.request.Request(
            self.base + path, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, json.loads(response.read())

    def test_status_and_actions_round_trip_over_http(self):
        status, _, body = self.get("/api/status")
        self.assertEqual(200, status)
        self.assertEqual(10, json.loads(body)["remaining_seconds"])
        _, started = self.post("/api/action", {"action": "toggle"})
        self.assertTrue(started["running"])
        self.moment[0] += 3
        _, _, polled = self.get("/api/status")
        self.assertEqual(7, json.loads(polled)["remaining_seconds"])

    def test_the_page_and_its_assets_are_served_with_their_types(self):
        for path, expected in (("/", "text/html"), ("/app.js", "text/javascript"),
                               ("/theme.css", "text/css")):
            status, headers, body = self.get(path)
            self.assertEqual(200, status)
            self.assertIn(expected, headers["Content-Type"])
            self.assertTrue(body)

    def test_an_unknown_action_answers_400_with_a_reason(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/action", {"action": "explode"})
        error = caught.exception
        self.addCleanup(error.close)
        self.assertEqual(400, error.code)
        self.assertIn("unknown action", json.loads(error.read())["error"])

    def test_a_client_that_drops_mid_request_is_not_an_error(self):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            probe = socket.create_connection(("127.0.0.1", self.server.server_address[1]),
                                             timeout=TIMEOUT)
            probe.sendall(b"GET /api/status HTTP/1.1\r\nHost: tempo\r\n")
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                             struct.pack("ii", 1, 0))
            probe.close()
            # The server is single threaded, so this request only completes after it has
            # finished dealing with the reset connection.
            status, _, _ = self.get("/api/status")
        self.assertEqual(200, status)
        self.assertNotIn("Traceback", captured.getvalue())

    def test_unknown_paths_answer_404(self):
        for method in ("GET", "POST"):
            request = urllib.request.Request(self.base + "/nope", method=method,
                                             data=b"{}" if method == "POST" else None)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=TIMEOUT)
            self.addCleanup(caught.exception.close)
            self.assertEqual(404, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
