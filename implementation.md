# Implementation Plan — Multi-Agent Diagnosis Support & Referral Router

## Overview

A FastAPI backend using **LangGraph** to orchestrate 4 sequential Claude API agents, paired with a simple chat frontend. The system takes a patient's symptom description, assesses urgency, generates ranked possible conditions, and routes to the appropriate specialist.

LangGraph models the pipeline as a state graph — each agent is a node, and the emergency short-circuit is a conditional edge from the triage node.

---

## Project Structure

```
Agentic_AI_Project/
├── backend/
│   ├── main.py               # FastAPI app, single POST /diagnose endpoint
│   ├── graph.py              # LangGraph StateGraph definition (nodes + edges)
│   ├── state.py              # GraphState TypedDict — shared state passed between nodes
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── intake.py         # Intake Agent node function
│   │   ├── triage.py         # Triage/Urgency Agent node function
│   │   ├── diagnosis.py      # Diagnosis Agent node function
│   │   └── referral.py       # Referral Router Agent node function
│   ├── prompts.py            # All system prompts in one place
│   ├── schemas.py            # Pydantic models for all JSON shapes
│   └── requirements.txt
├── frontend/
│   ├── index.html            # Single-page chat UI
│   ├── style.css
│   └── app.js                # Fetch calls to backend, renders referral card
└── implementation.md         # This file
```

---

## Phase 1 — Backend Scaffolding

### 1.1 `requirements.txt`
```
fastapi
uvicorn
anthropic
langgraph
langchain-anthropic
pydantic
python-dotenv
```

### 1.2 `schemas.py` — Pydantic models for every agent I/O

| Schema | Fields |
|---|---|
| `UserInput` | `message: str` |
| `StructuredSymptoms` | `symptoms: list[str]`, `duration: str`, `severity: str`, `age: str`, `history: str` |
| `TriageResult` | `urgency: Literal["emergency","urgent","routine"]`, `reason: str` |
| `PossibleCondition` | `name: str`, `likelihood: str`, `reasoning: str` |
| `DiagnosisResult` | `possible_conditions: list[PossibleCondition]`, `disclaimer: str` |
| `ReferralResult` | `specialist: str`, `reasoning: str` |
| `FinalOutput` | `structured_symptoms`, `triage`, `diagnosis` (optional), `referral` (optional), `emergency_message` (optional), agent trace metadata |

---

## Phase 2 — LangGraph State (`state.py`)

LangGraph passes a single shared state dict between all nodes. Every agent reads from and writes to this state.

```python
from typing import TypedDict, Optional
from schemas import StructuredSymptoms, TriageResult, DiagnosisResult, ReferralResult

class GraphState(TypedDict):
    user_message: str
    structured_symptoms: Optional[StructuredSymptoms]
    triage_result: Optional[TriageResult]
    diagnosis_result: Optional[DiagnosisResult]
    referral_result: Optional[ReferralResult]
    emergency_message: Optional[str]
    agent_trace: list[dict]       # tracks which agent ran + its output
```

---

## Phase 3 — Prompts (`prompts.py`)

Each prompt is a module-level string constant. No prompt logic lives anywhere else.

### `INTAKE_SYSTEM_PROMPT`
- Role: friendly medical intake assistant
- Task: extract `{symptoms, duration, severity, age, history}` from the user's free-text description
- If any field is missing/ambiguous, ask one clarifying question at a time (conversational)
- **Output:** JSON only, matching `StructuredSymptoms` schema
- Must never diagnose or suggest conditions

### `TRIAGE_SYSTEM_PROMPT`
- Role: emergency triage screener
- Task: scan `structured_symptoms` for red-flag patterns (chest pain, difficulty breathing, stroke signs, severe bleeding, altered consciousness, etc.)
- **Output:** JSON only — `{urgency, reason}` — one of three urgency levels
- This is the only agent permitted to declare an emergency

### `DIAGNOSIS_SYSTEM_PROMPT`
- Role: differential diagnosis generator
- Task: given `structured_symptoms`, produce 3–5 ranked possible conditions
- **Output:** JSON only — `{possible_conditions: [{name, likelihood, reasoning}], disclaimer}`
- Every output includes a disclaimer; framed as possibilities, never certainties

### `REFERRAL_SYSTEM_PROMPT`
- Role: specialist routing agent
- Task: given top condition(s) and urgency level, recommend the appropriate specialist type
- **Output:** JSON only — `{specialist, reasoning}`
- Never runs when urgency = "emergency" (enforced by the graph's conditional edge, not this prompt)

---

## Phase 4 — Agent Node Functions (`agents/`)

Each agent file exports one function that accepts and returns `GraphState`. LangGraph calls these as nodes.

```python
# Pattern for every agent node
def intake_node(state: GraphState) -> GraphState:
    client = ChatAnthropic(model="claude-sonnet-5")
    response = client.invoke([
        SystemMessage(content=INTAKE_SYSTEM_PROMPT),
        HumanMessage(content=state["user_message"])
    ])
    raw = response.content
    try:
        parsed = StructuredSymptoms.model_validate_json(raw)
    except ValidationError:
        # Retry once with a correction nudge, then raise
        ...
    state["structured_symptoms"] = parsed
    state["agent_trace"].append({"agent": "intake", "output": parsed.model_dump()})
    return state
```

- **`intake.py`** → `intake_node(state) -> state` — populates `structured_symptoms`
- **`triage.py`** → `triage_node(state) -> state` — populates `triage_result`
- **`diagnosis.py`** → `diagnosis_node(state) -> state` — populates `diagnosis_result`
- **`referral.py`** → `referral_node(state) -> state` — populates `referral_result`

---

## Phase 5 — LangGraph Pipeline (`graph.py`)

```python
from langgraph.graph import StateGraph, END
from state import GraphState
from agents.intake import intake_node
from agents.triage import triage_node
from agents.diagnosis import diagnosis_node
from agents.referral import referral_node

def route_after_triage(state: GraphState) -> str:
    if state["triage_result"].urgency == "emergency":
        return "emergency_end"
    return "diagnosis"

def emergency_node(state: GraphState) -> GraphState:
    state["emergency_message"] = (
        f"EMERGENCY: Call 911 or go to the nearest ER immediately. "
        f"Reason: {state['triage_result'].reason}"
    )
    return state

builder = StateGraph(GraphState)

builder.add_node("intake", intake_node)
builder.add_node("triage", triage_node)
builder.add_node("diagnosis", diagnosis_node)
builder.add_node("referral", referral_node)
builder.add_node("emergency_end", emergency_node)

builder.set_entry_point("intake")
builder.add_edge("intake", "triage")
builder.add_conditional_edges("triage", route_after_triage, {
    "emergency_end": "emergency_end",
    "diagnosis": "diagnosis",
})
builder.add_edge("diagnosis", "referral")
builder.add_edge("referral", END)
builder.add_edge("emergency_end", END)

graph = builder.compile()
```

The conditional edge on `"triage"` is the emergency short-circuit — agents 3 & 4 are never reached when urgency = "emergency".

---

## Phase 6 — FastAPI App (`main.py`)

- Single endpoint: `POST /diagnose`
- Request body: `UserInput`
- Invokes `graph.invoke({"user_message": ..., "agent_trace": []})`
- Response body: `FinalOutput` assembled from final graph state
- CORS enabled for local frontend dev
- `.env` file holds `ANTHROPIC_API_KEY`

---

## Phase 7 — Frontend (`frontend/`)

Single HTML page with:

1. **Chat input** — user types symptom description, hits Send
2. **Agent trace panel** — shows which agent ran and its raw JSON output (collapsible, for demo transparency)
3. **Referral card** — final summary card showing:
   - Urgency level (color-coded: red/orange/green)
   - Possible conditions list with likelihoods
   - Recommended specialist
   - Disclaimer
4. **Emergency state** — if urgency = "emergency", the entire UI switches to a red emergency banner with the message, hiding the referral card

Plain HTML/CSS/vanilla JS — no framework. One `fetch()` call to `POST /diagnose`.

---

## Phase 8 — Error Handling & Safety

- JSON parse failure on any agent: retry once with `"Respond with valid JSON only: <schema>"`, then return a `500` with a clear error message
- Emergency short-circuit: enforced by the LangGraph conditional edge — diagnosis and referral nodes are structurally unreachable when urgency = "emergency"
- All diagnosis output fields must include the disclaimer string — enforced in the `DiagnosisResult` schema (non-optional field)
- No medication, dosage, or treatment text anywhere in any prompt

---

## Implementation Order

| Step | Task | File(s) |
|---|---|---|
| 1 | Project folders + `requirements.txt` | `backend/` |
| 2 | Pydantic schemas | `schemas.py` |
| 3 | LangGraph state definition | `state.py` |
| 4 | System prompts | `prompts.py` |
| 5 | Agent node functions (intake → triage → diagnosis → referral) | `agents/*.py` |
| 6 | LangGraph graph definition + conditional edge | `graph.py` |
| 7 | FastAPI app + endpoint | `main.py` |
| 8 | Frontend UI | `frontend/` |
| 9 | End-to-end smoke test (routine + emergency paths) | manual |

---

## Out of Scope (for this version)

- RAG / vector DB / external medical knowledge base
- Authentication
- Database / persistence
- Multi-turn conversation memory beyond a single request
