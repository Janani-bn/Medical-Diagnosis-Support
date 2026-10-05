# Medical Diagnosis Support & Referral Router

A multi-agent AI system that takes a patient's symptom description, assesses urgency, generates a ranked list of possible conditions, and routes the patient to the appropriate medical specialist.

> **Disclaimer:** This is not a medical diagnostic tool. All outputs are possibilities to discuss with a licensed healthcare provider.

---

## What It Does

1. User describes their symptoms in plain text
2. A fast Jev pre-screen runs first — rejects non-medical input and immediately short-circuits obvious emergencies
3. Four specialized AI agents process the input sequentially through a LangGraph pipeline
4. If an emergency is detected, the pipeline short-circuits and returns an emergency message
5. Otherwise, the system returns possible conditions, a specialist recommendation, and Jev confidence scores

---

## Agent Workflow

```
User Input
    │
    ▼
[Pre-screen] Jev (TypeSafe)
    Checks: is this medical? is this an obvious emergency?
    │
    ├── obvious emergency ──► Return emergency message (skip all 4 agents)
    ├── not medical ────────► Return 400 error
    │
    ▼
[1] Intake Agent  —  Groq LLM
    Extracts structured data from free-text symptoms
    (symptoms, duration, severity, age, history)
    │
    ▼
[2] Triage Agent  —  Jev (TypeSafe)
    Classifies urgency → emergency | urgent | routine
    Returns calibrated confidence score + full probability distribution
    Auto-escalates to "urgent" if confidence < 50%
    │
    ├── emergency ──► Return emergency message (skip agents 3 & 4)
    │
    ▼
[3] Diagnosis Agent  —  Groq LLM
    Generates 3–5 ranked possible conditions with reasoning
    │
    ▼
[4] Referral Router Agent  —  Jev (TypeSafe)
    Picks specialist from a constrained list of 12 types (cannot invent names)
    Checks whether urgent care should also be recommended
    │
    ▼
Final Response (JSON) → displayed in the browser
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI (Python) |
| Agent orchestration | LangGraph |
| Classification agents | TypeSafe Jev (`typesafe-sdk`) — Triage + Referral |
| Generative agents | LangChain Groq (`langchain-groq`) — Intake + Diagnosis |
| LLM model | Qwen 3.8 27B via Groq API |
| Data validation | Pydantic |
| Environment config | python-dotenv |
| Frontend | HTML5, CSS3, Vanilla JavaScript |

---

## Why Jev for Triage and Referral?

The Triage and Referral agents are pure classification problems — they pick from a fixed set of options, not generate text. Jev is TypeSafe's System One model built specifically for this:

| | Groq (old) | Jev (current) |
|---|---|---|
| Output | Free-text JSON that needs parsing | Typed Python objects, no parsing |
| Hallucination | Can invent urgency labels or specialist names | Constrained to exactly the options you define |
| Confidence | None | Calibrated confidence score (0–1) on every decision |
| Retry logic | Required | Not needed |
| Safety escalation | Not possible | Low-confidence triage auto-escalates to "urgent" |

---

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI app — POST /diagnose + Jev pre-screen
│   ├── graph.py             # LangGraph pipeline definition
│   ├── state.py             # Shared GraphState TypedDict
│   ├── schemas.py           # Pydantic models for all agent I/O
│   ├── prompts.py           # System prompts for Groq agents
│   ├── requirements.txt
│   ├── .env.example         # Copy to .env and fill in both API keys
│   └── agents/
│       ├── intake.py        # Groq — text extraction
│       ├── triage.py        # Jev — urgency classification
│       ├── diagnosis.py     # Groq — condition generation
│       └── referral.py      # Jev — specialist routing
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- A [Groq API key](https://console.groq.com) (free tier: 14,400 requests/day)
- A [TypeSafe API key](https://console.typesafe.ai) (for Jev — Triage + Referral agents)

---

### 1. Clone the repo

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name/backend
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in both keys:

```
GROQ_API_KEY=gsk_...        # from console.groq.com
TYPESAFE_API_KEY=ts_...     # from console.typesafe.ai
```

### 4. Start the backend

```bash
uvicorn main:app --reload
```

The API will be running at `http://127.0.0.1:8000`.  
Interactive API docs: `http://127.0.0.1:8000/docs`

### 5. Open the frontend

Open `frontend/index.html` directly in your browser (double-click or drag into browser), or:

```bash
open ../frontend/index.html    # macOS
```

---

## What You See in the UI

After submitting symptoms, the results panel shows:

- **Urgency badge** — Emergency / Urgent / Routine
- **Escalation warning** — appears if Jev was uncertain and auto-elevated the urgency
- **Jev Triage Insights** — animated confidence bar + probability distribution across all three urgency levels
- **Possible conditions** — ranked list from the Diagnosis agent with likelihood badges
- **Recommended specialist** — with Jev confidence bar and a "Constrained to 12 specialist types" badge
- **Agent Speed Breakdown** — bar chart comparing Jev agents (purple) vs Groq agents (amber) with millisecond timings
- **Agent Trace** — collapsible raw JSON of every agent's output for debugging

---

## Safety Rules

- Emergency detection runs at two points: the Jev pre-screen (before any agents) and the Triage agent (after intake)
- Diagnosis output is always a list of possibilities — never a confirmed diagnosis
- Every diagnosis response includes a mandatory disclaimer
- No medication, dosage, or treatment instructions anywhere in the pipeline
- The Referral Router never runs when urgency is "emergency"
