/*
 * The browser half of Tempo.
 *
 * It owns no timer rules: the server settles phases and this file renders the snapshot it
 * returns, then posts one named action per button. Phase styling is driven by a data
 * attribute so every colour stays in theme.css.
 */
(function () {
  "use strict";

  var POLL_MS = 1000;
  var ACTIONS = { toggle: "toggle", skip: "skip", reset: "reset" };

  var card = document.querySelector(".card");
  var display = document.getElementById("timer-display");
  var phaseLabel = document.getElementById("phase-label");
  var dots = document.getElementById("cycle-dots");
  var runButton = document.getElementById("run-button");
  var summary = document.getElementById("session-summary");
  var statusLine = document.getElementById("status-line");

  var PHASE_NAMES = {
    "focus": "focus",
    "short-break": "short break",
    "long-break": "long break"
  };

  function formatClock(totalSeconds) {
    var seconds = Math.max(0, Math.round(totalSeconds));
    var minutes = Math.floor(seconds / 60);
    return String(minutes).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
  }

  function renderDots(position, length) {
    var markup = "";
    for (var index = 0; index < length; index += 1) {
      markup += '<li class="dot" data-filled="' + (index < position ? "yes" : "no") + '"></li>';
    }
    dots.innerHTML = markup;
  }

  function renderSummary(count) {
    if (count === 0) { return "no focus phases finished yet"; }
    return count + (count === 1 ? " focus phase done" : " focus phases done");
  }

  function render(status) {
    card.setAttribute("data-phase", status.phase);
    display.textContent = formatClock(status.remaining_seconds);
    phaseLabel.textContent = PHASE_NAMES[status.phase] || status.phase;
    runButton.textContent = status.running ? "Pause" : "Start";
    runButton.setAttribute("aria-pressed", status.running ? "true" : "false");
    document.title = formatClock(status.remaining_seconds) + " - Tempo";
    renderDots(status.cycle_position, status.cycle_length);
    summary.textContent = renderSummary(status.completed_focus);
    statusLine.textContent = "";
  }

  function fail(message) {
    statusLine.textContent = message;
  }

  function request(path, options) {
    return fetch(path, options).then(function (response) {
      if (!response.ok) { throw new Error("server returned " + response.status); }
      return response.json();
    });
  }

  function poll() {
    request("/api/status", { cache: "no-store" }).then(render).catch(function () {
      fail("server unreachable - is `python run.py` still running?");
    });
  }

  function send(action) {
    request("/api/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: action })
    }).then(render).catch(function () {
      fail("could not apply " + action);
    });
  }

  document.querySelectorAll("[data-action]").forEach(function (button) {
    button.addEventListener("click", function () {
      var action = ACTIONS[button.getAttribute("data-action")];
      if (action) { send(action); }
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === " " && event.target === document.body) {
      event.preventDefault();
      send(ACTIONS.toggle);
    }
  });

  poll();
  window.setInterval(poll, POLL_MS);
})();
