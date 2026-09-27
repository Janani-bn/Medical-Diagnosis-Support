# Tech Stack Explanation — Medical Diagnosis Support & Referral Router

This document explains every technology used in this project, what it does, and why it was chosen.

---

## Big Picture

The project is split into two parts:

- **Backend** — a Python server that runs the AI pipeline
- **Frontend** — a plain HTML page that talks to the backend

When a user types their symptoms and hits Send, the frontend sends the text to the backend. The backend runs it through 4 AI agents one by one and sends back a structured result. The frontend displays that result as a referral card.

---

## Backend Tech Stack

### 1. Python
The entire backend is written in Python. Python is the standard language for AI/ML work because almost every AI library and SDK is built for it first.

---

### 2. FastAPI
**File:** `main.py`
**What it is:** A modern Python web framework for building APIs.
**What it does here:** Exposes one endpoint — `POST /diagnose` — that the frontend calls. FastAPI receives the user's symptom message, passes it to the LangGraph pipeline, and returns the final JSON result.
**Why FastAPI:** It is fast, automatically generates API documentation at `/docs`, and works well with Python's async features. It also uses Pydantic natively for request/response validation.

---

### 3. Uvicorn
**What it is:** An ASGI web server for Python.
**What it does here:** Runs the FastAPI app. When you type `uvicorn main:app --reload`, Uvicorn is what actually starts the server and listens on `http://127.0.0.1:8000`.
**Why Uvicorn:** It is the standard server used with FastAPI. The `--reload` flag automatically restarts the server whenever you change a file, which is useful during development.

---

### 4. Pydantic
**File:** `schemas.py`
**What it is:** A Python data validation library.
**What it does here:** Defines the exact shape of every piece of data that flows through the pipeline. Every agent's input and output has a Pydantic model — `StructuredSymptoms`, `TriageResult`, `DiagnosisResult`, `ReferralResult`, and `FinalOutput`. If the AI returns malformed JSON, Pydantic catches it immediately with a clear error.
**Why Pydantic:** It enforces data contracts between agents. Without it, a bad response from one agent could silently corrupt everything downstream.

---

### 5. LangGraph
**File:** `graph.py`
**What it is:** A library from LangChain for building stateful, graph-based AI pipelines.
**What it does here:** Defines the entire agent pipeline as a directed graph with nodes and edges:
- Each agent (intake, triage, diagnosis, referral) is a **node**
- The flow between agents is an **edge**
- After the triage node, there is a **conditional edge** — if urgency is "emergency", the graph routes to `emergency_end` and stops. If not, it continues to diagnosis and referral.

This is the core orchestration layer. LangGraph manages the state, runs each node in order, and handles the branching logic.

**Why LangGraph:** It makes the emergency short-circuit a structural guarantee, not just an `if` statement. The diagnosis and referral nodes are literally unreachable when urgency is "emergency" — the graph's topology enforces it.

---

### 6. LangChain Core (`langchain-core`)
**What it is:** The base library that LangGraph and all LangChain integrations are built on.
**What it does here:** Provides `SystemMessage` and `HumanMessage` — the message objects used to structure conversations when calling the AI model. Every agent builds a list of these messages and sends them to the model.

```python
messages = [
    SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
    HumanMessage(content=symptoms_json)
]
```

---

### 7. LangChain Groq (`langchain-groq`)
**Files:** All 4 agent files in `agents/`
**What it is:** The LangChain integration for Groq's API.
**What it does here:** Provides `ChatGroq` — the client object used inside every agent to call the AI model. Each agent has its own `ChatGroq` instance pointing at the `qwen/qwen3.8-27b` model.

```python
_client = ChatGroq(model="qwen/qwen3.8-27b", timeout=30)
response = _client.invoke(messages)
```

**Why LangChain Groq:** It plugs directly into LangGraph and LangChain's message format, making the integration clean and consistent across all agents.

---

### 8. Groq API + Qwen 3.8 27B Model
**What it is:** Groq is an AI inference platform. Qwen 3.8 27B is the language model running on it.
**What it does here:** This is the actual AI brain behind all 4 agents. Every agent sends its prompt + input data to this model and gets a JSON response back. Groq runs inference extremely fast compared to most providers.
**Why Groq:** It has a generous free tier (14,400 requests/day), is very fast, and supports LangChain natively.
**Why Qwen 3.8 27B:** It was the best available model on this Groq account at the time of setup.

---

### 9. GraphState / TypedDict
**File:** `state.py`
**What it is:** A Python `TypedDict` — a dictionary with typed keys.
**What it does here:** Defines the shared state that flows through the entire LangGraph pipeline. Every agent reads from this state and writes its output back into it. By the end of the pipeline, the state contains everything — structured symptoms, triage result, diagnosis, referral, emergency message, and the agent trace.

```python
class GraphState(TypedDict):
    user_message: str
    structured_symptoms: Optional[StructuredSymptoms]
    triage_result: Optional[TriageResult]
    diagnosis_result: Optional[DiagnosisResult]
    referral_result: Optional[ReferralResult]
    emergency_message: Optional[str]
    agent_trace: list[dict]
```

---

### 10. System Prompts
**File:** `prompts.py`
**What it is:** Plain Python string constants.
**What it does here:** Each agent has a dedicated system prompt that tells the AI model exactly what its role is, what input it receives, and what JSON format it must return. All 4 prompts live in this one file — nothing else goes in here.
**Why a separate file:** Keeping prompts out of the orchestration logic makes them easy to find, read, and change without touching agent code.

---

### 11. python-dotenv
**File:** `.env`
**What it is:** A library that loads environment variables from a `.env` file.
**What it does here:** Reads `GROQ_API_KEY` from the `.env` file and makes it available to the app when it starts. This keeps the API key out of the code.

---

### 12. Virtual Environment (`venv`)
**Folder:** `backend/venv/`
**What it is:** An isolated Python environment.
**What it does here:** All the project's dependencies (FastAPI, LangGraph, etc.) are installed inside this folder, separate from the rest of your system's Python packages. Activated with `source venv/bin/activate`.
**Why:** Prevents dependency conflicts between projects and avoids the "externally managed environment" error on Mac.

---

## Frontend Tech Stack

### 13. HTML (`index.html`)
**What it is:** Standard HTML5 markup.
**What it does here:** Defines the structure of the page:
- A `<textarea>` for the user to type symptoms
- A `<button>` to submit
- A `<div>` for the emergency banner (hidden by default, shown in red when urgency = emergency)
- A referral card `<div>` showing urgency badge, conditions list, and specialist
- A `<details>` element for the collapsible agent trace panel
- A loading spinner shown while the API call is in progress

No framework. No build step. Just one HTML file.

---

### 14. CSS (`style.css`)
**What it is:** Plain CSS3.
**What it does here:** Styles the entire UI:
- Clean card-based layout with a light gray background
- Color-coded urgency badge — red for emergency, orange for urgent, green for routine
- Condition likelihood badges — red for high, orange for moderate, green for low
- Emergency banner — full red background that takes over the UI
- Loading spinner animation
- Dark-themed code block for the agent trace panel
- Responsive layout that works on any screen size

No CSS framework (no Bootstrap, no Tailwind). Pure CSS only.

---

### 15. JavaScript (`app.js`)
**What it is:** Plain vanilla JavaScript (ES6+).
**What it does here:**
- Listens for the Submit button click (or Enter key)
- Sends a `POST /diagnose` request to the backend using the `fetch()` API
- Shows a loading spinner while waiting
- When the response arrives, reads the JSON and decides what to render:
  - If `emergency_message` is present → shows the red emergency banner, hides the referral card
  - Otherwise → renders the urgency badge, conditions list, specialist, and disclaimer
- Populates the agent trace panel with the raw JSON from all agents

No framework (no React, no Vue). One `fetch()` call and plain DOM manipulation.

---

## How Everything Connects — Request Flow

```
User types symptoms → clicks Send
        │
        ▼
app.js: fetch("POST /diagnose", { message: "..." })
        │
        ▼
FastAPI (main.py): receives UserInput
        │
        ▼
LangGraph graph.invoke(initial_state)
        │
        ├── Node 1: intake_node (agents/intake.py)
        │     ChatGroq → INTAKE_SYSTEM_PROMPT + user_message
        │     → parses StructuredSymptoms JSON
        │     → writes to state["structured_symptoms"]
        │
        ├── Node 2: triage_node (agents/triage.py)
        │     ChatGroq → TRIAGE_SYSTEM_PROMPT + structured_symptoms
        │     → parses TriageResult JSON
        │     → writes to state["triage_result"]
        │
        ├── Conditional Edge: route_after_triage()
        │     if urgency == "emergency" → emergency_end node → END
        │     else → diagnosis node
        │
        ├── Node 3: diagnosis_node (agents/diagnosis.py)
        │     ChatGroq → DIAGNOSIS_SYSTEM_PROMPT + structured_symptoms
        │     → parses DiagnosisResult JSON (3-5 conditions)
        │     → writes to state["diagnosis_result"]
        │
        └── Node 4: referral_node (agents/referral.py)
              ChatGroq → REFERRAL_SYSTEM_PROMPT + conditions + urgency
              → parses ReferralResult JSON
              → writes to state["referral_result"]
                    │
                    ▼
            FastAPI assembles FinalOutput
                    │
                    ▼
            JSON response sent back to browser
                    │
                    ▼
            app.js renders referral card or emergency banner
```

---

## Dependency Summary

| Package | Version pinned? | Purpose |
|---|---|---|
| `fastapi` | No | Web framework / API server |
| `uvicorn` | No | ASGI server to run FastAPI |
| `langgraph` | No | Agent pipeline orchestration |
| `langchain-groq` | No | LangChain integration for Groq API |
| `langchain-core` | No | Base message types (SystemMessage, HumanMessage) |
| `pydantic` | No | Data validation and JSON schema enforcement |
| `python-dotenv` | No | Load API keys from .env file |

All installed inside `backend/venv/` via `pip install -r requirements.txt`.

---

## What is NOT used (and why)

| Technology | Why it was excluded |
|---|---|
| Database (PostgreSQL, SQLite, etc.) | Pipeline is stateless per request — nothing needs to be saved |
| LangChain Expression Language (LCEL) | LangGraph is used instead for explicit graph-based control flow |
| CrewAI / AutoGen | Overkill for a sequential pipeline; adds complexity without benefit |
| React / Vue / Angular | A single-page HTML form doesn't need a frontend framework |
| RAG / Vector DB | No external medical knowledge base in this version |
| Docker | Not needed for local development |
| Authentication | Out of scope for this version |

---

## Why Python Over Other Languages

Python was chosen as the backend language for this project. Here is a direct comparison against the other realistic alternatives.

---

### Python vs JavaScript / Node.js

| Factor | Python | JavaScript / Node.js |
|---|---|---|
| AI/ML ecosystem | Best in class — LangChain, LangGraph, every major AI SDK ships Python first | Secondary support — most SDKs have JS versions but they lag behind |
| LangGraph | Official Python library, full feature support | No official LangGraph port for Node.js |
| Pydantic | Native to Python, deeply integrated with FastAPI | No equivalent with the same depth and speed |
| Code readability | Clean, readable syntax — good for prompt engineering and agent logic | Can be verbose, especially with async/await chains |
| When to prefer Node | Real-time apps, heavy frontend/backend sharing, WebSocket servers | — |
| Verdict | Better for AI pipelines | Better for real-time web apps |

**Conclusion:** For an AI agent pipeline, Python is the clear choice. LangGraph does not exist for Node.js. The entire AI toolchain is built around Python first.

---

### Python vs Java

| Factor | Python | Java |
|---|---|---|
| AI library support | Extensive — LangChain, LangGraph, Groq SDK, TypeSafe SDK all support Python natively | Very limited — most AI libraries have no Java SDK |
| Development speed | Fast — one line in Python often takes 10 in Java | Slow to prototype — verbose boilerplate everywhere |
| FastAPI equivalent | FastAPI is extremely fast to set up and use | Spring Boot works but requires far more configuration |
| Pydantic equivalent | Built-in, simple, tight FastAPI integration | Jackson/Hibernate exist but are more complex |
| Type safety | Python with Pydantic gives runtime + schema validation | Java is statically typed but overly rigid for AI work |
| When to prefer Java | High-traffic enterprise systems, Android apps | — |
| Verdict | Much faster to build AI pipelines | Better for enterprise-scale backend systems |

**Conclusion:** Java has no competitive AI ecosystem for 2024-era tools. Building this in Java would mean writing custom integrations for everything LangChain and LangGraph provide out of the box.

---

### Python vs Go

| Factor | Python | Go |
|---|---|---|
| AI ecosystem | Dominant | Virtually none — no LangChain, no LangGraph |
| Development speed | Fast — minimal boilerplate | Fast for systems code, slow for AI work |
| Performance | Slower raw execution | Much faster raw execution |
| Concurrency | Async/await, works well for I/O bound AI calls | Excellent goroutines |
| When to prefer Go | High-performance APIs, infrastructure tools, CLI tools | — |
| Verdict | The only viable choice for this stack | Great language, wrong ecosystem for AI |

**Conclusion:** Go has no AI agent framework. You would be building everything from scratch. That is not a practical choice when Python has LangGraph, LangChain, and Pydantic ready to use.

---

### Python vs Ruby / PHP

Neither Ruby nor PHP has meaningful AI/ML tooling in 2024. LangChain, LangGraph, and every major AI SDK either do not support these languages or offer experimental, unmaintained ports. They are not viable choices for an AI pipeline project.

---

### Summary — Why Python Wins for This Project

| Requirement | Why Python covers it best |
|---|---|
| LangGraph for agent orchestration | Python only — no other language has it |
| LangChain Groq integration | Python SDK is the primary and best-supported one |
| FastAPI for the API server | Python native — fast to build, automatic docs, Pydantic built in |
| Pydantic for JSON validation | Python native — tight schema enforcement between agents |
| TypeSafe SDK (future Jev integration) | Python SDK is the primary SDK |
| Rapid prototyping | Python's concise syntax means less code, fewer bugs, faster iteration |
| Community and documentation | Largest AI/ML community by far — answers to every problem exist |

Python is not chosen out of habit. It is chosen because the entire modern AI agent toolchain — LangGraph, LangChain, Pydantic, FastAPI, and every LLM provider SDK — treats Python as the first-class language. Using any other language for this stack would mean giving up most of the tools that make this project possible.
