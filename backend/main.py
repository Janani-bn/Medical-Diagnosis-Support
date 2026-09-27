from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from schemas import UserInput, FinalOutput
from graph import graph

load_dotenv()

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
