# Medical Diagnosis Support & Referral Router

A multi-agent AI system that takes a patient's symptom description, assesses urgency, generates a ranked list of possible conditions, and routes the patient to the appropriate medical specialist.

> **Disclaimer:** This is not a medical diagnostic tool. All outputs are possibilities to discuss with a licensed healthcare provider.

---

## What It Does

1. User describes their symptoms in plain text
2. Four specialized AI agents process the input sequentially
3. If an emergency is detected, the pipeline short-circuits and returns an emergency message immediately
4. Otherwise, the system returns possible conditions and a specialist recommendation

---

## Agent Workflow

```
User Input
    │
    ▼
[1] Intake Agent
    Extracts structured data from free-text symptoms
    (symptoms, duration, severity, age, history)
    │
    ▼
[2] Triage Agent
    Assesses urgency → emergency | urgent | routine
    │
    ├── emergency ──► Return emergency message immediately (skip agents 3 & 4)
    │
    ▼
[3] Diagnosis Agent
    Generates 3–5 ranked possible conditions with reasoning
    │
    ▼
[4] Referral Router Agent
    Recommends the appropriate specialist type
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
| LLM integration | LangChain Groq (`langchain-groq`) |
| LLM model | Qwen 3.8 27B via Groq API |
| Data validation | Pydantic |
| Environment config | python-dotenv |
| Frontend | HTML5, CSS3, Vanilla JavaScript |

---

## LLM & API

- **Provider:** [Groq](https://console.groq.com)
- **Model:** `qwen/qwen3.8-27b`
- **Why Groq:** Free tier with 14,400 requests/day, extremely fast inference
- **Each request makes 4 sequential LLM calls** (one per agent) or 2 if an emergency is detected early

---

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI app — POST /diagnose endpoint
│   ├── graph.py             # LangGraph pipeline definition
│   ├── state.py             # Shared GraphState TypedDict
│   ├── schemas.py           # Pydantic models for all agent I/O
│   ├── prompts.py           # All 4 system prompts
│   ├── requirements.txt
│   ├── .env.example         # Copy to .env and add your API key
│   └── agents/
│       ├── intake.py
│       ├── triage.py
│       ├── diagnosis.py
│       └── referral.py
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

---

## Getting Started

**1. Clone the repo**
```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name/backend
```

**2. Create a virtual environment and install dependencies**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Add your API key**
```bash
cp .env.example .env
# Open .env and paste your Groq API key
```

Get a free Groq API key at [console.groq.com](https://console.groq.com)

**4. Start the backend**
```bash
uvicorn main:app --reload
```

**5. Open the frontend**

Open `frontend/index.html` directly in your browser.

The API docs are available at `http://127.0.0.1:8000/docs`.

---

## Safety Rules

- Emergency detection always runs first and short-circuits the pipeline
- Diagnosis output is always a list of possibilities — never a confirmed diagnosis
- Every diagnosis response includes a mandatory disclaimer
- No medication, dosage, or treatment instructions anywhere in the pipeline
