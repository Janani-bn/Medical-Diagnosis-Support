from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typesafe_sdk import TypeSafeClient, Noul

from schemas import UserInput, FinalOutput
from graph import graph

load_dotenv()


def _prescreen(message: str) -> dict:
    """Returns {"is_medical": float, "is_emergency": float} probabilities."""
    with TypeSafeClient() as client:
        response = client.system_one(
            model="jev-latest",
            state={"message": message},
            questions={
                "is_medical": Noul(
                    instructions="Is this message a genuine medical symptom description?"
                ),
                "is_emergency_keywords": Noul(
                    instructions="Does this message contain obvious emergency keywords like 'can't breathe', 'chest pain', 'unconscious', 'stroke', 'not breathing', 'severe bleeding'?"
                )
            }
        )
    return {
        "is_medical": response.nouls["is_medical"].noul,
        "is_emergency": response.nouls["is_emergency_keywords"].noul
    }

app = FastAPI(title="Medical Diagnosis Support & Referral Router")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/diagnose", response_model=FinalOutput)
async def diagnose(user_input: UserInput):
    import asyncio
    try:
        # Fast pre-screen: catch obvious non-medical or emergency messages before the pipeline
        screen = await asyncio.get_event_loop().run_in_executor(None, _prescreen, user_input.message)

        if screen["is_medical"] < 0.3:
            raise HTTPException(status_code=400, detail="Please describe a medical symptom.")

        if screen["is_emergency"] > 0.9:
            return FinalOutput(
                structured_symptoms=None,
                triage=None,
                diagnosis=None,
                referral=None,
                emergency_message="This appears to be a medical emergency. Call 911 or go to the nearest emergency room immediately.",
                agent_trace=[{"agent": "prescreening", "output": {"fast_path": "emergency_keywords_detected"}}],
            )

        initial_state = {
            "user_message": user_input.message,
            "structured_symptoms": None,
            "triage_result": None,
            "diagnosis_result": None,
            "referral_result": None,
            "emergency_message": None,
            "agent_trace": [],
        }
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, graph.invoke, initial_state),
            timeout=120
        )
        return FinalOutput(
            structured_symptoms=result.get("structured_symptoms"),
            triage=result.get("triage_result"),
            diagnosis=result.get("diagnosis_result"),
            referral=result.get("referral_result"),
            emergency_message=result.get("emergency_message"),
            agent_trace=result.get("agent_trace", []),
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out. The AI model took too long to respond.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
