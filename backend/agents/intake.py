from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from state import GraphState
from schemas import StructuredSymptoms
from prompts import INTAKE_SYSTEM_PROMPT

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


def intake_node(state: GraphState) -> GraphState:
    messages = [
        SystemMessage(content=INTAKE_SYSTEM_PROMPT),
        HumanMessage(content=state["user_message"])
    ]
    raw = _call_model(messages)

    try:
        parsed = StructuredSymptoms.model_validate_json(raw)
    except ValidationError:
        raw = _call_model(messages + [
            HumanMessage(content="Respond with valid JSON only matching the schema. No extra text.")
        ])
        parsed = StructuredSymptoms.model_validate_json(raw)

    return {
        **state,
        "structured_symptoms": parsed,
        "agent_trace": state["agent_trace"] + [{"agent": "intake", "output": parsed.model_dump()}]
    }
