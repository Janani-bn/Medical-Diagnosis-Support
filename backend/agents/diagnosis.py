import time
from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from state import GraphState
from schemas import DiagnosisResult
from prompts import DIAGNOSIS_SYSTEM_PROMPT

_client = ChatGroq(model="qwen/qwen3.8-27b", timeout=30)


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block["text"]
    return str(content)


def _call_model(messages: list) -> str:
    response = _client.invoke(messages)
    return _extract_text(response.content)


def diagnosis_node(state: GraphState) -> GraphState:
    symptoms = state["structured_symptoms"]
    messages = [
        SystemMessage(content=DIAGNOSIS_SYSTEM_PROMPT),
        HumanMessage(content=symptoms.model_dump_json())
    ]

    start = time.time()
    raw = _call_model(messages)
    try:
        parsed = DiagnosisResult.model_validate_json(raw)
    except ValidationError:
        raw = _call_model(messages + [
            HumanMessage(content="Respond with valid JSON only matching the schema. No extra text.")
        ])
        parsed = DiagnosisResult.model_validate_json(raw)
    duration_ms = int((time.time() - start) * 1000)

    return {
        **state,
        "diagnosis_result": parsed,
        "agent_trace": state["agent_trace"] + [{
            "agent": "diagnosis",
            "model": "groq/qwen3",
            "output": parsed.model_dump(),
            "duration_ms": duration_ms
        }]
    }
