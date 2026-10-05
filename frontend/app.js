const API_URL = "http://localhost:8000/diagnose";

async function submitSymptoms() {
  const input = document.getElementById("symptom-input").value.trim();
  if (!input) return;

  const btn = document.getElementById("submit-btn");
  btn.disabled = true;

  document.getElementById("results").classList.add("hidden");
  document.getElementById("emergency-banner").classList.add("hidden");
  document.getElementById("loading").classList.remove("hidden");

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: input }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Server error");
    }

    const data = await res.json();
    renderResult(data);
  } catch (err) {
    alert("Error: " + err.message);
  } finally {
    document.getElementById("loading").classList.add("hidden");
    btn.disabled = false;
  }
}

function renderResult(data) {
  if (data.emergency_message) {
    document.getElementById("emergency-text").textContent = data.emergency_message;
    document.getElementById("emergency-banner").classList.remove("hidden");
    renderTrace(data.agent_trace);
    document.getElementById("results").classList.remove("hidden");
    document.getElementById("referral-card").classList.add("hidden");
    document.getElementById("urgency-badge-container").classList.add("hidden");
    document.getElementById("jev-triage-panel").classList.add("hidden");
    document.getElementById("escalation-warning").classList.add("hidden");
    document.getElementById("speed-panel").classList.add("hidden");
    return;
  }

  document.getElementById("referral-card").classList.remove("hidden");
  document.getElementById("urgency-badge-container").classList.remove("hidden");

  // Urgency badge
  const badge = document.getElementById("urgency-badge");
  const urgency = data.triage?.urgency || "routine";
  badge.textContent = urgency;
  badge.className = urgency;
  document.getElementById("urgency-reason").textContent = "";

  // Pull triage and referral entries from agent_trace
  const triageTrace = (data.agent_trace || []).find(t => t.agent === "triage");
  const referralTrace = (data.agent_trace || []).find(t => t.agent === "referral");

  // ── Feature 2: Escalation warning ──────────────────────────────────────────
  const escalationEl = document.getElementById("escalation-warning");
  if (triageTrace?.escalated) {
    escalationEl.classList.remove("hidden");
  } else {
    escalationEl.classList.add("hidden");
  }

  // ── Feature 1 + 3: Triage confidence bar + probability distribution ────────
  const jevTriagePanel = document.getElementById("jev-triage-panel");
  if (triageTrace?.confidence != null) {
    jevTriagePanel.classList.remove("hidden");

    const confPct = Math.round(triageTrace.confidence * 100);
    document.getElementById("triage-conf-fill").style.width = confPct + "%";
    document.getElementById("triage-conf-fill").style.background = confColor(triageTrace.confidence);
    document.getElementById("triage-conf-pct").textContent = confPct + "%";

    // Probability bars
    const probs = triageTrace.probabilities || {};
    ["emergency", "urgent", "routine"].forEach(level => {
      const pct = Math.round((probs[level] || 0) * 100);
      document.getElementById("prob-bar-" + level).style.width = pct + "%";
      document.getElementById("prob-val-" + level).textContent = pct + "%";
    });
  } else {
    jevTriagePanel.classList.add("hidden");
  }

  // Conditions list
  const list = document.getElementById("conditions-list");
  list.innerHTML = "";
  (data.diagnosis?.possible_conditions || []).forEach((c) => {
    const li = document.createElement("li");
    const likelihoodClass = "likelihood-" + (c.likelihood || "low").toLowerCase();
    li.innerHTML = `
      <div>
        <span class="condition-name">${c.name}</span>
        <span class="condition-likelihood ${likelihoodClass}">${c.likelihood}</span>
      </div>
      <div class="condition-reasoning">${c.reasoning}</div>
    `;
    list.appendChild(li);
  });

  document.getElementById("disclaimer-text").textContent =
    data.diagnosis?.disclaimer || "";

  // Specialist
  document.getElementById("specialist-name").textContent =
    data.referral?.specialist || "—";
  document.getElementById("specialist-reasoning").textContent =
    data.referral?.reasoning || "";

  // ── Feature 1 + 4: Specialist confidence bar + constrained badge ───────────
  const jevReferralPanel = document.getElementById("jev-referral-panel");
  if (referralTrace?.specialist_confidence != null) {
    jevReferralPanel.classList.remove("hidden");

    const specPct = Math.round(referralTrace.specialist_confidence * 100);
    document.getElementById("specialist-conf-fill").style.width = specPct + "%";
    document.getElementById("specialist-conf-pct").textContent = specPct + "%";
  } else {
    jevReferralPanel.classList.add("hidden");
  }

  // ── Feature 5: Speed comparison panel ─────────────────────────────────────
  renderSpeedPanel(data.agent_trace || []);

  renderTrace(data.agent_trace);
  document.getElementById("results").classList.remove("hidden");
}

function renderSpeedPanel(trace) {
  const panel = document.getElementById("speed-panel");
  const rowsEl = document.getElementById("speed-rows");

  const agents = ["intake", "triage", "diagnosis", "referral"];
  const entries = agents.map(name => trace.find(t => t.agent === name)).filter(Boolean);

  if (entries.length === 0) {
    panel.classList.add("hidden");
    return;
  }

  const maxMs = Math.max(...entries.map(e => e.duration_ms || 0), 1);

  rowsEl.innerHTML = entries.map(e => {
    const ms = e.duration_ms || 0;
    const barPct = Math.round((ms / maxMs) * 100);
    const isJev = e.model === "jev-latest";
    const barClass = isJev ? "speed-bar-jev" : "speed-bar-groq";
    const modelTag = isJev
      ? `<span class="model-tag model-jev">Jev</span>`
      : `<span class="model-tag model-groq">Groq</span>`;
    return `
      <div class="speed-row">
        <span class="speed-agent">${capitalize(e.agent)}</span>
        ${modelTag}
        <div class="speed-track">
          <div class="speed-bar ${barClass}" style="width:${barPct}%"></div>
        </div>
        <span class="speed-ms">${ms} ms</span>
      </div>
    `;
  }).join("");

  panel.classList.remove("hidden");
}

function confColor(conf) {
  if (conf >= 0.8) return "#22c55e";
  if (conf >= 0.5) return "#f59e0b";
  return "#ef4444";
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function renderTrace(trace) {
  document.getElementById("trace-output").textContent = JSON.stringify(trace, null, 2);
}

// Allow Enter key to submit (Shift+Enter for newline)
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("symptom-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitSymptoms();
    }
  });
});
