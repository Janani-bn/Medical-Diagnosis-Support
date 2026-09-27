# CLAUDE.md — Multi-Agent Diagnosis Support & Referral Router

This file gives Claude Code the context it needs to work on this project correctly. Read this before making changes.

## Project Overview

A multi-agent AI system that takes a patient's symptom description through a conversational intake, assesses urgency, generates a ranked list of possible conditions, and routes the patient to the appropriate medical specialist.

This is **not** a diagnostic tool that gives medical advice as fact — every output must be framed as "possibilities to discuss with a doctor." Emergency detection always overrides everything else.

No RAG / vector DB / external medical knowledge base is used. Each agent reasons directly using the LLM's own knowledge via careful prompt engineering.

## Architecture

Sequential pipeline of 4 specialized agents, coordinated by an orchestrator. Each agent is a separate function/module with its own system prompt and a narrow responsibility. Agents hand off structured JSON to each other — never raw free text between stages.

```
User Input
   │
   ▼
[1] Intake Agent  ───────────► structured_symptoms (JSON)
   │
   ▼
[2] Triage/Urgency Agent  ───► urgency_level ("emergency" | "urgent" | "routine")
   │
   ├── if emergency ──► short-circuit: return emergency message immediately, skip agents 3 & 4
   │
   ▼
[3] Diagnosis Agent  ────────► possible_conditions (ranked list, JSON)
   │
   ▼
[4] Referral Router Agent  ──► recommended_specialist (JSON)
   │
   ▼
Orchestrator assembles final_output (JSON) → returned to frontend
```

### Agent responsibilities

| Agent | Input | Output | Responsibility |
|---|---|---|---|
| Intake Agent | Raw user conversation/text | `structured_symptoms` JSON: `{symptoms: [...], duration, severity, age, history}` | Ask clarifying questions if info is missing. Never diagnoses. |
| Triage/Urgency Agent | `structured_symptoms` | `{urgency: "emergency" \| "urgent" \| "routine", reason}` | Flags red-flag symptoms (chest pain, severe bleeding, difficulty breathing, stroke signs, etc.). This check runs first and can short-circuit the pipeline. |
| Diagnosis Agent | `structured_symptoms` | `{possible_conditions: [{name, likelihood, reasoning}, ...]}` (3–5 items) | Ranked differential list only. Always framed as possibilities, never certainties. |
| Referral Router Agent | `possible_conditions` + `urgency` | `{specialist, reasoning}` | Maps top condition(s) to the right specialist type. If urgency is "emergency," this agent is skipped entirely by the orchestrator. |
| Orchestrator | User input | Final combined JSON | Calls agents in order, handles the emergency short-circuit, passes structured data between stages, assembles final response. |

## Code Conventions

- Each agent = one function (or one class method) with its own dedicated system prompt string. Keep system prompts in a separate `prompts.py` (or `prompts/` folder if they grow long) — don't inline long prompt strings inside orchestration logic.
- All agent-to-agent handoffs must be valid JSON. Every agent's system prompt should explicitly instruct the model to respond in JSON only, matching a fixed schema. Validate/parse this JSON before passing to the next agent; handle parse failures gracefully (retry once, then fail with a clear error rather than crashing).
- No agent other than the Triage Agent should ever declare something an emergency or make the final urgency call — keep that logic centralized so behavior stays predictable.
- Disclaimers are not optional decoration — every diagnosis-related output field must include a disclaimer string reinforcing "this is not a medical diagnosis."

## Tech Stack

- **Backend:** FastAPI (Python) orchestrating sequential Claude API calls — no agent framework (LangGraph/CrewAI/AutoGen) unless explicitly requested later.
- **LLM:** Claude API, one call per agent, each with its own system prompt.
- **Frontend:** Simple chat/form UI showing intake conversation + a final "referral card" summary. Should also display which agent produced which part of the output (for transparency/demo purposes).
- **No database, no RAG, no vector store** for this version. Keep the pipeline stateless per request unless told otherwise.

## Safety Rules (do not relax these without being asked explicitly)

1. Emergency detection in the Triage Agent runs before diagnosis/referral logic and can short-circuit the entire pipeline.
2. Diagnosis Agent output is always a list of *possibilities*, never a single confirmed diagnosis, and never omits the "discuss with a doctor" framing.
3. Never let the Referral Router Agent run instead of returning an emergency message when urgency = "emergency."
4. Do not add real medical dosage, medication, or treatment instructions anywhere in this pipeline — the system routes to specialists, it does not prescribe or treat.

## What Claude Code should do when asked to extend this project

- When adding a new agent, follow the existing pattern: dedicated system prompt in `prompts.py`, dedicated function, JSON in/JSON out, wired into the orchestrator in sequence.
- When modifying an existing agent's prompt, preserve the JSON schema unless the task explicitly asks to change it, since downstream agents depend on that shape.
- When asked to add RAG, a vector DB, or an external knowledge base later, treat it as a new optional layer feeding into the Diagnosis Agent specifically — don't restructure the rest of the pipeline to accommodate it.
