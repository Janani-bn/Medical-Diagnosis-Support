import time
from dotenv import load_dotenv
load_dotenv()

from typesafe_sdk import TypeSafeClient, Choice, Noul

from state import GraphState
from schemas import ReferralResult

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

SPECIALIST_COUNT = len(SPECIALIST_LIST)


def referral_node(state: GraphState) -> GraphState:
    conditions = state["diagnosis_result"].possible_conditions
    urgency = state["triage_result"].urgency

    start = time.time()
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
    duration_ms = int((time.time() - start) * 1000)

    specialist_key = response.choices["specialist"].choice
    specialist_confidence = response.choices["specialist"].confidence
    urgent_care_probability = response.nouls["needs_urgent_care"].noul

    specialist_name = specialist_key.replace("_", " ").title()
    if urgent_care_probability > 0.75 and urgency == "urgent":
        specialist_name = "Urgent Care + " + specialist_name

    referral_result = ReferralResult(
        specialist=specialist_name,
        reasoning=f"Selected based on top condition: {conditions[0].name}. Confidence: {specialist_confidence:.2f}"
    )

    return {
        **state,
        "referral_result": referral_result,
        "agent_trace": state["agent_trace"] + [{
            "agent": "referral",
            "model": "jev-latest",
            "output": referral_result.model_dump(),
            "specialist_confidence": specialist_confidence,
            "urgent_care_probability": urgent_care_probability,
            "specialist_count": SPECIALIST_COUNT,
            "duration_ms": duration_ms
        }]
    }
