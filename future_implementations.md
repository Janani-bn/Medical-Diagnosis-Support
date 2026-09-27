# Future Implementation — Integrating TypeSafe Jev for Fast & Accurate Decisions

---

## Why Jev?

The current system uses a general-purpose language model (Groq + Qwen) for every agent, including the ones that don't need to generate text — they just need to make a decision. This is like hiring a novelist to answer yes/no questions. It works, but it is slower, less predictable, and more expensive than necessary.

**TypeSafe Jev** is a System One model built specifically for structured decisions. Instead of generating text and reasoning explanations, it evaluates input and returns **typed answers with calibrated probabilities**. It cannot hallucinate an option that wasn't given to it — answers are constrained to exactly what you define.

For this medical pipeline, two agents — Triage and Referral Router — are pure decision problems. They do not need to generate text. They need to pick the right answer from a defined set, fast and reliably. Jev is the right tool for exactly that.

---

## Current vs. Future Architecture

### Current (Groq for all agents)
```
Intake     → Groq LLM (text extraction)
Triage     → Groq LLM (urgency classification)     ← overkill for a 3-way decision
Diagnosis  → Groq LLM (condition generation)
Referral   → Groq LLM (specialist routing)          ← overkill for a routing decision
```

### Future (Hybrid: Groq + Jev)
```
Intake     → Groq LLM (text extraction — still needs generation)
Triage     → Jev      (urgency classification — perfect fit for Choice)
Diagnosis  → Groq LLM (condition generation — still needs generation)
Referral   → Jev      (specialist routing — perfect fit for Choice)
```

Jev replaces Groq for the two classification agents. Groq stays for the two agents that genuinely need to generate text.

---

## What Jev Is

Jev is TypeSafe's flagship **System One** model. It works through three primitives:

### Choice
Picks one option from a defined set. Returns the selected option, a probability for every option, and a confidence score (0–1).
Best for: routing, classification, categorization.

### Noul
Answers a yes/no question. Returns a single probability (0 = definitely no, 1 = definitely yes, 0.5 = uncertain).
Best for: flag detection, condition checks, binary filters.

### Score
Rates something along a described spectrum. Returns a position between levels with probabilities.
Best for: severity assessment, ranking, grading.

**Key advantage:** Multiple questions over the same input can be asked in a single API call and Jev evaluates them in parallel — adding more questions barely increases response time.

---

## How Jev Fits Each Agent

---

### Agent 2 — Triage Agent (Jev replaces Groq)

**Current behavior:** Sends symptoms to Groq, asks it to return `{urgency, reason}` JSON.
**Problem:** Groq can return inconsistent phrasing, needs JSON parsing, can fail validation.

**With Jev:**
Use a `Choice` primitive with three options. Jev cannot return anything outside these three — hallucination is structurally impossible.

```python
from typesafe_sdk import Choice, TypeSafeClient
from dotenv import load_dotenv
load_dotenv()

def triage_node(state: GraphState) -> GraphState:
    symptoms = state["structured_symptoms"]

    with TypeSafeClient() as client:
        response = client.system_one(
            model="jev-latest",
            state={
                "symptoms": symptoms.symptoms,
                "duration": symptoms.duration,
                "severity": symptoms.severity,
                "age": symptoms.age,
                "history": symptoms.history
            },
            questions={
                "urgency": Choice(
                    instructions="What is the urgency level for this patient based on their symptoms?",
                    criteria={
                        "emergency": "Life-threatening symptoms requiring immediate 911 or ER — chest pain, difficulty breathing, stroke signs (facial droop, arm weakness, slurred speech), severe uncontrolled bleeding, loss of consciousness, anaphylaxis, worst headache of life",
                        "urgent": "Needs same-day or next-day medical attention but not immediately life-threatening — high fever, moderate pain, symptoms worsening over hours",
                        "routine": "Can safely wait for a scheduled appointment — mild symptoms, stable condition, no red flags present"
                    }
                )
            }
        )

    urgency = response.choices["urgency"].choice
    confidence = response.choices["urgency"].confidence
    probabilities = response.choices["urgency"].probabilities

    triage_result = TriageResult(
        urgency=urgency,
        reason=f"Jev confidence: {confidence:.2f} | Probabilities: {probabilities}"
    )

    return {
        **state,
        "triage_result": triage_result,
        "agent_trace": state["agent_trace"] + [{
            "agent": "triage",
            "output": triage_result.model_dump(),
            "confidence": confidence
        }]
    }
```

**What changes:**
- No JSON parsing needed — Jev returns typed Python objects
- No retry logic needed — answer is always one of the three defined options
- Confidence score is available — if confidence < 0.5, we can flag it for human review
- Significantly faster than a full LLM call

---

### Agent 4 — Referral Router Agent (Jev replaces Groq)

**Current behavior:** Sends conditions + urgency to Groq, asks it to return `{specialist, reasoning}` JSON.
**Problem:** Groq invents specialist names and formats inconsistently. Routing decisions should be deterministic.

**With Jev:**
Use a `Choice` primitive with all specialist types defined. Add a `Noul` to check if a second specialist is also worth mentioning.

```python
from typesafe_sdk import Choice, Noul, TypeSafeClient

SPECIALIST_LIST = {
    "general_practitioner": "Primary care for common illnesses, infections, and general health concerns",
    "cardiologist": "Heart conditions — chest pain, palpitations, hypertension, cardiovascular disease",
    "neurologist": "Brain and nervous system — headaches, migraines, seizures, numbness, stroke follow-up",
    "dermatologist": "Skin conditions — rashes, blisters, infections, acne, lesions",
    "pulmonologist": "Lung and respiratory — asthma, COPD, breathing difficulties, chronic cough",
    "gastroenterologist": "Digestive system — abdominal pain, reflux, bowel issues, liver concerns",
    "orthopedist": "Bones and joints — fractures, joint pain, sports injuries, back pain",
    "psychiatrist": "Mental health — anxiety, depression, panic disorders, mood disorders",
    "endocrinologist": "Hormones and metabolism — diabetes, thyroid, adrenal conditions",
    "urologist": "Urinary tract and kidneys — UTI, kidney stones, frequent urination",
    "ent_specialist": "Ear, nose and throat — sinus problems, hearing issues, throat conditions",
    "urgent_care": "Same-day care for urgent but non-emergency conditions"
}

def referral_node(state: GraphState) -> GraphState:
    conditions = state["diagnosis_result"].possible_conditions
    urgency = state["triage_result"].urgency

    with TypeSafeClient() as client:
        response = client.system_one(
            model="jev-latest",
            state={
                "top_condition": conditions[0].name,
                "top_condition_reasoning": conditions[0].reasoning,
                "all_conditions": [c.name for c in conditions],
                "urgency": urgency
            },
            questions={
                "specialist": Choice(
                    instructions="Which specialist type is most appropriate for the patient's top condition and urgency level?",
                    criteria=SPECIALIST_LIST
                ),
                "needs_urgent_care": Noul(
                    instructions="Should this patient be directed to urgent care given the urgency level and severity of symptoms?"
                )
            }
        )

    specialist_key = response.choices["specialist"].choice
    specialist_name = specialist_key.replace("_", " ").title()
    needs_urgent = response.nouls["needs_urgent_care"].probability > 0.75

    if needs_urgent and urgency == "urgent":
        specialist_name = "Urgent Care + " + specialist_name

    referral_result = ReferralResult(
        specialist=specialist_name,
        reasoning=f"Selected based on top condition: {conditions[0].name}. Confidence: {response.choices['specialist'].confidence:.2f}"
    )

    return {
        **state,
        "referral_result": referral_result,
        "agent_trace": state["agent_trace"] + [{
            "agent": "referral",
            "output": referral_result.model_dump(),
            "specialist_confidence": response.choices["specialist"].confidence,
            "urgent_care_probability": response.nouls["needs_urgent_care"].probability
        }]
    }
```

**What changes:**
- Specialist list is explicitly defined — Jev cannot invent a specialist that isn't in the list
- Two questions asked in one API call (specialist + urgent care check) — evaluated in parallel
- Confidence score exposed in the agent trace
- Deterministic, consistent output every time

---

### Using Confidence for Safety Escalation

One of Jev's biggest advantages is the confidence score. This enables a safety layer that the current system doesn't have:

```python
# In triage_node — after getting Jev's answer
confidence = response.choices["urgency"].confidence

if confidence < 0.5:
    # Jev is uncertain — treat as urgent to be safe
    triage_result = TriageResult(
        urgency="urgent",
        reason=f"Low confidence triage ({confidence:.2f}) — elevated to urgent as precaution"
    )
elif urgency == "emergency" and confidence > 0.85:
    # High confidence emergency — short-circuit immediately
    pass
```

This means:
- If Jev is **very confident** (0.9+) → act automatically
- If Jev is **moderately confident** (0.5–0.9) → proceed but flag in trace
- If Jev is **uncertain** (<0.5) → escalate to a safer option or flag for human review

---

## Additional Jev Opportunities

Beyond replacing the two agents, Jev can add new capabilities:

### Pre-screening with Noul (before Intake Agent)
```python
# Quick check before running the full pipeline
response = client.system_one(
    model="jev-latest",
    state={"message": user_message},
    questions={
        "is_medical": Noul(
            instructions="Is this message a genuine medical symptom description?"
        ),
        "is_emergency_keywords": Noul(
            instructions="Does this message contain obvious emergency keywords like 'can't breathe', 'chest pain', 'unconscious', 'stroke'?"
        )
    }
)

if response.nouls["is_emergency_keywords"].probability > 0.9:
    # Fast-path: return emergency message without running all 4 agents
    return emergency_response()

if response.nouls["is_medical"].probability < 0.3:
    # Not a medical query — reject early
    return HTTPException(400, "Please describe a medical symptom.")
```

### Severity Scoring with Score
```python
"severity_score": Score(
    instructions="How severe are these symptoms overall?",
    criteria={
        "minimal": "Barely noticeable, does not affect daily life",
        "mild": "Noticeable but manageable, minor impact on daily life",
        "moderate": "Clearly affects daily activities, needs attention",
        "severe": "Significantly impacts ability to function normally",
        "critical": "Completely debilitating or dangerous"
    }
)
```

---

## Setup Instructions (Future)

When implementing this, the following changes are needed:

**1. Install TypeSafe SDK**
```bash
pip install typesafe-sdk
```

**2. Add to `requirements.txt`**
```
typesafe-sdk
```

**3. Add API key to `.env`**
```
GROQ_API_KEY=gsk_...          # still needed for intake + diagnosis
TYPESAFE_API_KEY=ts_...       # get from console.typesafe.ai
```

**4. Replace agent files**
- `agents/triage.py` → rewrite using `TypeSafeClient` + `Choice`
- `agents/referral.py` → rewrite using `TypeSafeClient` + `Choice` + `Noul`
- `agents/intake.py` → keep Groq (needs text generation)
- `agents/diagnosis.py` → keep Groq (needs text generation)

---

## Benefits Summary

| Metric | Current (Groq only) | Future (Groq + Jev) |
|---|---|---|
| Triage reliability | Depends on LLM prompt following | Constrained to 3 defined options — cannot hallucinate |
| Referral consistency | LLM invents specialist names | Constrained to defined specialist list |
| Response time | 4 full LLM calls | 2 LLM calls + 2 fast Jev calls |
| Confidence visibility | None | Confidence score on every Jev decision |
| Safety escalation | No | Low-confidence triage auto-escalates to urgent |
| Retry complexity | JSON parsing + retries on all agents | Jev returns typed objects — no parsing, no retries |
| Cost | 4 LLM tokens per request | 2 LLM calls + cheaper Jev calls for decisions |

---

## What Does NOT Change

- The LangGraph graph structure stays the same — nodes and edges are unchanged
- Intake and Diagnosis agents stay on Groq — they need text generation
- The Pydantic schemas stay the same — `TriageResult` and `ReferralResult` shapes are preserved
- The frontend stays the same — it only sees the final JSON output
- The emergency short-circuit logic stays the same — LangGraph's conditional edge still enforces it

---

## Summary

Jev does not replace the entire pipeline. It replaces the two agents that are fundamentally classification problems — Triage and Referral. For those two agents, Jev is strictly better: faster, more reliable, hallucination-proof, and gives confidence scores that enable smarter safety escalation. Groq continues to handle the two agents that actually need to generate text — Intake and Diagnosis.
