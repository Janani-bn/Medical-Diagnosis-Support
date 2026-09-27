from langgraph.graph import StateGraph, END

from state import GraphState
from agents.intake import intake_node
from agents.triage import triage_node
from agents.diagnosis import diagnosis_node
from agents.referral import referral_node


def emergency_node(state: GraphState) -> GraphState:
    return {
        **state,
        "emergency_message": (
            f"EMERGENCY: Call 911 or go to the nearest emergency room immediately. "
            f"Reason: {state['triage_result'].reason}"
        ),
        "agent_trace": state["agent_trace"] + [{"agent": "emergency_short_circuit", "output": {"message": "Pipeline stopped — emergency detected"}}]
    }


def route_after_triage(state: GraphState) -> str:
    if state["triage_result"].urgency == "emergency":
        return "emergency_end"
    return "diagnosis"


builder = StateGraph(GraphState)

builder.add_node("intake", intake_node)
builder.add_node("triage", triage_node)
builder.add_node("diagnosis", diagnosis_node)
builder.add_node("referral", referral_node)
builder.add_node("emergency_end", emergency_node)

builder.set_entry_point("intake")
builder.add_edge("intake", "triage")
builder.add_conditional_edges(
    "triage",
    route_after_triage,
    {
        "emergency_end": "emergency_end",
        "diagnosis": "diagnosis",
    }
)
builder.add_edge("diagnosis", "referral")
builder.add_edge("referral", END)
builder.add_edge("emergency_end", END)

graph = builder.compile()
