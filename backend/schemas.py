from typing import Literal, Optional
from pydantic import BaseModel


class UserInput(BaseModel):
    message: str


class StructuredSymptoms(BaseModel):
    symptoms: list[str]
    duration: str
    severity: str
    age: str
    history: str


class TriageResult(BaseModel):
    urgency: Literal["emergency", "urgent", "routine"]
    reason: str


class PossibleCondition(BaseModel):
    name: str
    likelihood: str
    reasoning: str


class DiagnosisResult(BaseModel):
    possible_conditions: list[PossibleCondition]
    disclaimer: str


class ReferralResult(BaseModel):
    specialist: str
    reasoning: str


class FinalOutput(BaseModel):
    structured_symptoms: Optional[StructuredSymptoms] = None
    triage: Optional[TriageResult] = None
    diagnosis: Optional[DiagnosisResult] = None
    referral: Optional[ReferralResult] = None
    emergency_message: Optional[str] = None
    agent_trace: list[dict] = []
