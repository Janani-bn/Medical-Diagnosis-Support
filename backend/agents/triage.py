import time
from dotenv import load_dotenv
load_dotenv()

from typesafe_sdk import TypeSafeClient, Choice

from state import GraphState
from schemas import TriageResult


def triage_node(state: GraphState) -> GraphState:
    symptoms = state["structured_symptoms"]

    start = time.time()
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
    duration_ms = int((time.time() - start) * 1000)

    urgency = response.choices["urgency"].choice
    confidence = response.choices["urgency"].confidence
    probabilities = dict(response.choices["urgency"].probabilities)

    escalated = False
    if confidence < 0.5 and urgency == "routine":
        urgency = "urgent"
        escalated = True
        reason = f"Low-confidence triage ({confidence:.2f}) — elevated to urgent as precaution | Probabilities: {probabilities}"
    else:
        reason = f"Jev confidence: {confidence:.2f} | Probabilities: {probabilities}"

    triage_result = TriageResult(urgency=urgency, reason=reason)

    return {
        **state,
        "triage_result": triage_result,
        "agent_trace": state["agent_trace"] + [{
            "agent": "triage",
            "model": "jev-latest",
            "output": triage_result.model_dump(),
            "confidence": confidence,
            "probabilities": probabilities,
            "escalated": escalated,
            "duration_ms": duration_ms
        }]
    }
