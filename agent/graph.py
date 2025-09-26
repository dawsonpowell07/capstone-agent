from langgraph.graph import StateGraph, MessagesState
from langgraph.types import interrupt, Command
from langgraph.constants import END
from agent.nodes.flight_agent import flight_agent
from agent.nodes.hotel_agent import hotel_agent
from agent.nodes.activity_agent import activity_agent
from typing import Annotated, Literal
import operator
from agent.state import State


# ---- Approval Handlers (explicit per-agent) ----
def human_approve_flights(state: State) -> Command[Literal["approved_path_flights", "rejected_path_flights"]]:
    decision = interrupt(
        {
            "question": "Approve flight results?",
            "messages": state.get("messages", []),
        }
    )
    if decision == "approve":
        return Command(goto="approved_path_flights", update={"flight_decision": "approved"})
    else:
        # Add the feedback as a message so the agent sees it
        return Command(
            goto="rejected_path_flights", 
            update={
                "flight_decision": "rejected",
                "messages": [{"role": "user", "content": decision}]
            }
        )


def human_approve_hotels(state: State) -> Command[Literal["approved_path_hotels", "rejected_path_hotels"]]:
    decision = interrupt(
        {
            "question": "Approve hotel results?",
            "messages": state.get("messages", []),
        }
    )
    if decision == "approve":
        return Command(goto="approved_path_hotels", update={"hotel_decision": "approved"})
    else:
        return Command(goto="rejected_path_hotels", update={"hotel_decision": "rejected"})


def human_approve_activities(state: State) -> Command[Literal["approved_path_activities", "rejected_path_activities"]]:
    decision = interrupt(
        {
            "question": "Approve activity results?",
            "messages": state.get("messages", []),
        }
    )
    if decision == "approve":
        return Command(goto="approved_path_activities", update={"activity_decision": "approved"})
    else:
        return Command(goto="rejected_path_activities", update={"activity_decision": "rejected"})
    
# ---- Post-decision Handlers ----
def approved_node(state: State):
    print("✅ Approved path taken.")
    return state


def rejected_node(state: State):
    print("❌ Rejected path taken.")
    return state


# ---- User Info Context ----
def user_info(state: State):
    # In real life, pull from DB or service
    return {"user_info": "male 21 years old, likes hiking and food"}


# ---- Build the graph ----
builder = StateGraph(State)

builder.add_node("user_info", user_info)

# Agents
builder.add_node("flight_agent", flight_agent)
builder.add_node("hotel_agent", hotel_agent)
builder.add_node("activity_agent", activity_agent)

# Approval nodes
builder.add_node("human_approve_flights", human_approve_flights)
builder.add_node("human_approve_hotels", human_approve_hotels)
builder.add_node("human_approve_activities", human_approve_activities)

# Approved / Rejected nodes
builder.add_node("approved_path_flights", approved_node)
builder.add_node("rejected_path_flights", rejected_node)

builder.add_node("approved_path_hotels", approved_node)
builder.add_node("rejected_path_hotels", rejected_node)

builder.add_node("approved_path_activities", approved_node)
builder.add_node("rejected_path_activities", rejected_node)

# ---- Explicit Edges ----
builder.set_entry_point("user_info")
builder.add_edge("user_info", "flight_agent")

# Flight flow
builder.add_edge("flight_agent", "human_approve_flights")
builder.add_edge("approved_path_flights", "hotel_agent")
builder.add_edge("rejected_path_flights", "flight_agent")

# Hotel flow
builder.add_edge("hotel_agent", "human_approve_hotels")
builder.add_edge("approved_path_hotels", "activity_agent")
builder.add_edge("rejected_path_hotels", "hotel_agent")

# Activity flow
builder.add_edge("activity_agent", "human_approve_activities")
builder.add_edge("approved_path_activities", END)
builder.add_edge("rejected_path_activities", "activity_agent")

# ---- Compile ----
graph = builder.compile()