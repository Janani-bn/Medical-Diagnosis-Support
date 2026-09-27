from typing import Optional, TypedDict
from schemas import StructuredSymptoms, TriageResult, DiagnosisResult, ReferralResult


class GraphState(TypedDict):
    user_message: str
    structured_symptoms: Optional[StructuredSymptoms]
    triage_result: Optional[TriageResult]
    diagnosis_result: Optional[DiagnosisResult]
    referral_result: Optional[ReferralResult]
    emergency_message: Optional[str]
    agent_trace: list[dict]
