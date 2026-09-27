# System Architecture — Medical Diagnosis Support & Referral Router

---

## Overview

This system is a **multi-agent AI pipeline** built around a sequential, stateful graph. A user submits a symptom description in natural language. The system processes it through four specialized AI agents — each with a single, narrow responsibility — and returns a structured medical referral response.

The architecture follows a **pipeline pattern with a conditional short-circuit**: agents run in a fixed sequence, but the pipeline can terminate early if an emergency is detected, skipping all downstream agents entirely.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│                   (Browser — Static HTML)                       │
│                                                                 │
│   ┌──────────────────┐          ┌──────────────────────────┐   │
│   │  Symptom Input   │          │     Result Display       │   │
│   │  (textarea)      │          │  - Urgency Badge         │   │
│   │                  │          │  - Conditions List       │   │
│   │  [Send Button]   │          │  - Specialist Card       │   │
│   └────────┬─────────┘          │  - Emergency Banner      │   │
│            │ POST /diagnose     │  - Agent Trace Panel     │   │
│            │ { message: "..." } └──────────────────────────┘   │
└────────────┼────────────────────────────────────────────────────┘
             │ HTTP Request (JSON)
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                          BACKEND                                │
│                  (FastAPI + Python Server)                      │
│                                                                 │
│   POST /diagnose                                                │
│   ┌──────────────────────────────────────────────────────────┐ │
│   │                    LangGraph Pipeline                    │ │
│   │                                                          │ │
│   │  ┌──────────┐   ┌──────────┐   ┌──────────┐             │ │
│   │  │  Intake  │──▶│  Triage  │──▶│Diagnosis │             │ │
│   │  │  Agent   │   │  Agent   │   │  Agent   │             │ │
│   │  └──────────┘   └────┬─────┘   └────┬─────┘             │ │
│   │                      │              │                    │ │
│   │              emergency│         ┌───▼──────┐             │ │
│   │                  ┌───▼────┐     │ Referral │             │ │
│   │                  │  STOP  │     │  Agent   │             │ │
│   │                  └────────┘     └──────────┘             │ │
│   └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
             │ HTTP Response (JSON)
             ▼
        Browser renders result
```

---

## Layer Breakdown

### Layer 1 — Frontend (Presentation Layer)

| Component | Technology | Responsibility |
|---|---|---|
| `index.html` | HTML5 | Page structure — input form, result card, emergency banner |
| `style.css` | CSS3 | Visual layout, color-coded urgency, responsive design |
| `app.js` | Vanilla JavaScript | Sends API request, renders result, handles emergency state |

The frontend is completely stateless. It holds no data between requests. Every Submit triggers a fresh API call. The frontend's only job is to display whatever the backend returns.

---

### Layer 2 — API Layer

| Component | Technology | Responsibility |
|---|---|---|
| `main.py` | FastAPI | Single `POST /diagnose` endpoint, request/response handling |
| `schemas.py` | Pydantic | Validates request body (`UserInput`) and response shape (`FinalOutput`) |

FastAPI receives the request, validates it against the `UserInput` schema, invokes the LangGraph pipeline, and wraps the result into a `FinalOutput` response. If anything fails, it returns a structured error with an HTTP status code. A 120-second overall timeout prevents the request from hanging indefinitely.

---

### Layer 3 — Orchestration Layer (LangGraph)

| Component | Technology | Responsibility |
|---|---|---|
| `graph.py` | LangGraph StateGraph | Defines nodes, edges, conditional routing |
| `state.py` | Python TypedDict | Shared state passed between all agent nodes |

This is the core of the architecture. LangGraph builds a directed graph where:

- Each agent is a **node**
- The sequence between agents is an **edge**
- The emergency branch is a **conditional edge**

The graph is compiled once at startup (`graph = builder.compile()`) and reused for every request. Each request gets its own fresh `GraphState` instance so there is no shared state between concurrent users.

```
[intake] ──► [triage] ──► conditional edge ──► [emergency_end] ──► END
                                    │
                                    └──────────► [diagnosis] ──► [referral] ──► END
```

The conditional edge is evaluated after triage runs. If `urgency == "emergency"`, the graph routes to `emergency_end` and the pipeline terminates. The diagnosis and referral nodes are **structurally unreachable** in this path — LangGraph's graph topology enforces this, not an `if` statement in code.

---

### Layer 4 — Agent Layer

Each agent is an isolated Python function (a LangGraph node) with its own system prompt, its own LLM client, and a single responsibility. Agents do not call each other directly — they only read from and write to the shared `GraphState`.

#### Agent 1 — Intake Agent
```
File:       agents/intake.py
Input:      state["user_message"] (raw free text from user)
Output:     state["structured_symptoms"] (StructuredSymptoms JSON)
Prompt:     INTAKE_SYSTEM_PROMPT
Model:      qwen/qwen3.8-27b via Groq
Role:       Converts messy free-text symptom descriptions into clean structured data.
            Extracts: symptoms list, duration, severity, age, medical history.
            Never diagnoses or suggests conditions.
```

#### Agent 2 — Triage Agent
```
File:       agents/triage.py
Input:      state["structured_symptoms"]
Output:     state["triage_result"] (TriageResult JSON)
Prompt:     TRIAGE_SYSTEM_PROMPT
Model:      qwen/qwen3.8-27b via Groq
Role:       Scans structured symptoms for red-flag emergency patterns.
            Returns one of three urgency levels: emergency | urgent | routine.
            This is the ONLY agent permitted to declare an emergency.
            Its output determines which path the graph takes next.
```

#### Agent 3 — Diagnosis Agent
```
File:       agents/diagnosis.py
Input:      state["structured_symptoms"]
Output:     state["diagnosis_result"] (DiagnosisResult JSON)
Prompt:     DIAGNOSIS_SYSTEM_PROMPT
Model:      qwen/qwen3.8-27b via Groq
Role:       Generates a ranked list of 3–5 possible conditions with likelihoods
            and clinical reasoning. Always framed as possibilities, never certainties.
            Always includes a disclaimer. Never runs when urgency = "emergency".
```

#### Agent 4 — Referral Router Agent
```
File:       agents/referral.py
Input:      state["diagnosis_result"] + state["triage_result"]
Output:     state["referral_result"] (ReferralResult JSON)
Prompt:     REFERRAL_SYSTEM_PROMPT
Model:      qwen/qwen3.8-27b via Groq
Role:       Maps the top condition(s) and urgency level to the appropriate
            specialist type. Never recommends specific doctors or clinics.
            Never prescribes medications or treatments.
            Never runs when urgency = "emergency".
```

---

### Layer 5 — LLM Layer

| Component | Details |
|---|---|
| Provider | Groq |
| Model | qwen/qwen3.8-27b |
| Integration | langchain-groq → ChatGroq |
| Calls per request | 4 (one per agent, sequential) |
| Timeout per call | 30 seconds |
| Retry policy | Retry once only on JSON ValidationError; never retry on API errors |

Each agent makes exactly one LLM API call per request (two if the first response fails JSON validation). Calls are sequential — agent 2 cannot start until agent 1 finishes, because agent 2 needs agent 1's output.

---

## Data Flow

```
User Input (string)
        │
        ▼
┌───────────────────┐
│   UserInput       │  { "message": "I have chest pain..." }
│   (Pydantic)      │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  StructuredSymp-  │  { symptoms: [...], duration: "...",
│  toms (Pydantic)  │    severity: "...", age: "...", history: "..." }
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   TriageResult    │  { urgency: "emergency" | "urgent" | "routine",
│   (Pydantic)      │    reason: "..." }
└────────┬──────────┘
         │
    ┌────┴──────────────────────┐
    │ emergency?                │ not emergency?
    ▼                           ▼
emergency_message         DiagnosisResult
(string)                  { possible_conditions: [
                              { name, likelihood, reasoning },
                              ...
                          ], disclaimer: "..." }
                                │
                                ▼
                          ReferralResult
                          { specialist: "...", reasoning: "..." }
                                │
                                ▼
                    ┌───────────────────────┐
                    │     FinalOutput       │
                    │     (Pydantic)        │
                    │  - structured_symptoms│
                    │  - triage             │
                    │  - diagnosis          │
                    │  - referral           │
                    │  - emergency_message  │
                    │  - agent_trace        │
                    └───────────────────────┘
```

---

## State Schema

The `GraphState` TypedDict is the single source of truth as it travels through the pipeline. Every agent reads only the fields it needs and adds its own output.

```
GraphState {
    user_message:         str                        ← set at pipeline start
    structured_symptoms:  StructuredSymptoms | None  ← set by intake agent
    triage_result:        TriageResult | None         ← set by triage agent
    diagnosis_result:     DiagnosisResult | None      ← set by diagnosis agent
    referral_result:      ReferralResult | None       ← set by referral agent
    emergency_message:    str | None                 ← set by emergency_end node
    agent_trace:          list[dict]                 ← appended by every agent
}
```

Fields start as `None` and are populated as the pipeline progresses. In the emergency path, `diagnosis_result` and `referral_result` remain `None` in the final output.

---

## Safety Architecture

Three safety rules are enforced at the architecture level, not just in prompts:

### 1. Emergency Short-Circuit
The LangGraph conditional edge guarantees that when `urgency == "emergency"`, the diagnosis and referral nodes are never invoked. This is a graph topology constraint — it cannot be bypassed by a bad prompt or model hallucination.

### 2. Single Source of Truth for Urgency
Only the Triage Agent's system prompt grants permission to declare an emergency. No other agent's prompt mentions urgency levels or emergency detection. This centralizes the most critical safety decision.

### 3. Mandatory Disclaimer
The `DiagnosisResult` Pydantic schema has a `disclaimer` field that is non-optional (`str`, not `Optional[str]`). The diagnosis agent cannot return a valid response without it. Pydantic rejects any JSON that omits this field.

---

## Request Lifecycle

```
1. Browser sends POST /diagnose { "message": "..." }
2. FastAPI validates request with UserInput Pydantic model
3. FastAPI creates fresh GraphState with user_message and empty fields
4. LangGraph starts pipeline — runs intake_node
5. intake_node calls Groq API → gets StructuredSymptoms JSON → writes to state
6. LangGraph runs triage_node
7. triage_node calls Groq API → gets TriageResult JSON → writes to state
8. LangGraph evaluates conditional edge:
     a. urgency == "emergency" → runs emergency_end node → pipeline ends
     b. urgency != "emergency" → runs diagnosis_node
9. diagnosis_node calls Groq API → gets DiagnosisResult JSON → writes to state
10. LangGraph runs referral_node
11. referral_node calls Groq API → gets ReferralResult JSON → writes to state
12. Pipeline ends — LangGraph returns final state
13. FastAPI assembles FinalOutput from final state
14. FastAPI returns JSON response to browser
15. app.js reads response and renders the UI
```

Total LLM API calls per request: **4** (routine/urgent path) or **2** (emergency path).

---

## Error Handling Strategy

| Error Type | Handling |
|---|---|
| JSON parse failure from LLM | Retry once with a correction prompt. If second attempt also fails, raise exception → FastAPI returns 500 |
| LLM API error (rate limit, auth) | Raised immediately — no retry. FastAPI returns 500 with the error message |
| Request timeout (>120s total) | FastAPI returns 504 with "Request timed out" message |
| Single agent timeout (>30s) | LangChain raises timeout exception → FastAPI returns 500 |
| Invalid request body | Pydantic validation error → FastAPI returns 422 automatically |

---

## Folder Structure

```
Agentic_AI_Project/
│
├── backend/
│   ├── main.py            ← FastAPI app + /diagnose endpoint
│   ├── graph.py           ← LangGraph StateGraph definition
│   ├── state.py           ← GraphState TypedDict
│   ├── schemas.py         ← All Pydantic models
│   ├── prompts.py         ← All 4 system prompts
│   ├── requirements.txt   ← Python dependencies
│   ├── .env               ← GROQ_API_KEY (not committed)
│   └── agents/
│       ├── __init__.py
│       ├── intake.py      ← Agent 1
│       ├── triage.py      ← Agent 2
│       ├── diagnosis.py   ← Agent 3
│       └── referral.py    ← Agent 4
│
└── frontend/
    ├── index.html         ← Page structure
    ├── style.css          ← All styles
    └── app.js             ← API call + DOM rendering
```

---

## Design Decisions

| Decision | Reasoning |
|---|---|
| Sequential pipeline over parallel agents | Each agent depends on the previous agent's output. Parallelism is not possible here. |
| LangGraph over plain Python orchestration | Conditional edges enforce the emergency short-circuit at the graph topology level, not in application code. |
| One LLM client per agent file | Keeps agents isolated. Changing one agent's model or config does not affect others. |
| All prompts in one file (`prompts.py`) | Makes prompt engineering changes easy to find and review without digging into agent logic. |
| JSON-only agent responses | Structured JSON enforced by both the system prompt and Pydantic validation. Prevents downstream agents from receiving malformed input. |
| Stateless per request | No database, no session storage. Each request is fully independent. Simplifies scaling and debugging. |
| Plain HTML/CSS/JS frontend | No build tooling needed. Open the file directly in a browser. Keeps the demo simple and portable. |
