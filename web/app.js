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
  var ACTIONS = {
    toggle: "toggle",
    skip: "skip",
    reset: "reset",
    sound: "sound",
    settings: "settings",
    "save-settings": "save-settings",
    "close-settings": "close-settings"
  };

  var card = document.querySelector(".card");
  var display = document.getElementById("timer-display");
  var phaseLabel = document.getElementById("phase-label");
  var dots = document.getElementById("cycle-dots");
  var runButton = document.getElementById("run-button");
  var soundButton = document.getElementById("sound-button");
  var settingsButton = document.getElementById("settings-button");
  var summary = document.getElementById("session-summary");
  var analyticsSummary = document.getElementById("analytics-summary");
  var statusLine = document.getElementById("status-line");

  var settingsPanel = document.getElementById("settings-panel");
  var focusInput = document.getElementById("focus-input");
  var shortBreakInput = document.getElementById("short-break-input");
  var longBreakInput = document.getElementById("long-break-input");
  var cycleInput = document.getElementById("cycle-input");

  var lastPhaseIndex = null;
  var soundEnabled = true;
  var settingsOpen = false;

  try {
    var stored = localStorage.getItem("tempo-sound");
    if (stored !== null) { soundEnabled = stored === "true"; }
  } catch (e) {}

  var audioContext = null;
  function getAudioContext() {
    if (!audioContext && (window.AudioContext || window.webkitAudioContext)) {
      var AudioCtx = window.AudioContext || window.webkitAudioContext;
      audioContext = new AudioCtx();
    }
    if (audioContext && audioContext.state === "suspended") {
      audioContext.resume();
    }
    return audioContext;
  }

  function playChime(kind) {
    if (!soundEnabled) { return; }
    var ctx = getAudioContext();
    if (!ctx) { return; }
    try {
      var now = ctx.currentTime;
      var notes = kind === "focus" ? [659.25, 523.25] : [523.25, 659.25];
      notes.forEach(function (freq, index) {
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, now + index * 0.15);
        gain.gain.setValueAtTime(0.12, now + index * 0.15);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + index * 0.15 + 0.32);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + index * 0.15);
        osc.stop(now + index * 0.15 + 0.33);
      });
    } catch (e) {}
  }

  function updateSoundButton() {
    if (soundButton) {
      soundButton.textContent = soundEnabled ? "Sound on" : "Sound off";
      soundButton.setAttribute("aria-pressed", soundEnabled ? "true" : "false");
    }
  }
  updateSoundButton();

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

  function renderAnalytics(status) {
    if (!analyticsSummary) { return; }
    var todayMins = Math.round((status.today_focus_seconds || 0) / 60);
    var hrs = Math.floor(todayMins / 60);
    var mins = todayMins % 60;
    var durationText = hrs > 0 ? (hrs + "h " + mins + "m") : (mins + "m");
    var count = status.today_focus_count || 0;
    analyticsSummary.textContent = "Today: " + count + (count === 1 ? " interval (" : " intervals (") + durationText + ")";
  }

  function renderSettingsValues(status) {
    if (settingsOpen || !focusInput) { return; }
    if (status.focus_seconds) { focusInput.value = Math.round(status.focus_seconds / 60); }
    if (status.short_break_seconds) { shortBreakInput.value = Math.round(status.short_break_seconds / 60); }
    if (status.long_break_seconds) { longBreakInput.value = Math.round(status.long_break_seconds / 60); }
    if (status.cycle_length) { cycleInput.value = status.cycle_length; }
  }

  function render(status) {
    if (lastPhaseIndex !== null && status.phase_index !== lastPhaseIndex) {
      playChime(status.phase);
    }
    lastPhaseIndex = status.phase_index;
    card.setAttribute("data-phase", status.phase);
    display.textContent = formatClock(status.remaining_seconds);
    phaseLabel.textContent = PHASE_NAMES[status.phase] || status.phase;
    runButton.textContent = status.running ? "Pause" : "Start";
    runButton.setAttribute("aria-pressed", status.running ? "true" : "false");
    document.title = formatClock(status.remaining_seconds) + " - Tempo";
    renderDots(status.cycle_position, status.cycle_length);
    summary.textContent = renderSummary(status.completed_focus);
    renderAnalytics(status);
    renderSettingsValues(status);
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

  function toggleSettings(force) {
    settingsOpen = typeof force === "boolean" ? force : !settingsOpen;
    if (settingsPanel) {
      if (settingsOpen) {
        settingsPanel.classList.remove("hidden");
      } else {
        settingsPanel.classList.add("hidden");
      }
    }
    if (settingsButton) {
      settingsButton.setAttribute("aria-expanded", settingsOpen ? "true" : "false");
    }
  }

  function saveSettings() {
    var fMins = Math.max(1, Math.min(180, parseInt(focusInput.value, 10) || 25));
    var sbMins = Math.max(1, Math.min(60, parseInt(shortBreakInput.value, 10) || 5));
    var lbMins = Math.max(1, Math.min(60, parseInt(longBreakInput.value, 10) || 15));
    var cycle = Math.max(1, Math.min(12, parseInt(cycleInput.value, 10) || 4));

    send("configure", {
      focus_seconds: fMins * 60,
      short_break_seconds: sbMins * 60,
      long_break_seconds: lbMins * 60,
      cycle_length: cycle
    });
    toggleSettings(false);
  }

  function send(action, params) {
    getAudioContext();
    if (action === ACTIONS.sound) {
      soundEnabled = !soundEnabled;
      try { localStorage.setItem("tempo-sound", String(soundEnabled)); } catch (e) {}
      updateSoundButton();
      if (soundEnabled) { playChime("preview"); }
      return;
    }
    if (action === ACTIONS.settings) {
      toggleSettings();
      return;
    }
    if (action === ACTIONS["close-settings"]) {
      toggleSettings(false);
      return;
    }
    if (action === ACTIONS["save-settings"]) {
      saveSettings();
      return;
    }

    var payload = Object.assign({ action: action }, params || {});
    request("/api/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
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
