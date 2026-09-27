import json
from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from state import GraphState
from schemas import ReferralResult
from prompts import REFERRAL_SYSTEM_PROMPT

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


def referral_node(state: GraphState) -> GraphState:
    payload = {
        "possible_conditions": state["diagnosis_result"].model_dump()["possible_conditions"],
        "urgency": state["triage_result"].model_dump()["urgency"]
    }
    messages = [
        SystemMessage(content=REFERRAL_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(payload))
    ]
    raw = _call_model(messages)

    try:
        parsed = ReferralResult.model_validate_json(raw)
    except ValidationError:
        raw = _call_model(messages + [
            HumanMessage(content="Respond with valid JSON only matching the schema. No extra text.")
        ])
        parsed = ReferralResult.model_validate_json(raw)

    return {
        **state,
        "referral_result": parsed,
        "agent_trace": state["agent_trace"] + [{"agent": "referral", "output": parsed.model_dump()}]
    }
