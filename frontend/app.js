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
    return;
  }

  document.getElementById("referral-card").classList.remove("hidden");
  document.getElementById("urgency-badge-container").classList.remove("hidden");

  // Urgency badge
  const badge = document.getElementById("urgency-badge");
  const urgency = data.triage?.urgency || "routine";
  badge.textContent = urgency;
  badge.className = urgency;
  document.getElementById("urgency-reason").textContent = data.triage?.reason || "";

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

  renderTrace(data.agent_trace);
  document.getElementById("results").classList.remove("hidden");
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
