from typing import Callable
from langgraph.graph import StateGraph, MessagesState
from langgraph.types import interrupt, Command
from langgraph.constants import END

# Import the agents you already created
from agent.nodes.flight_agent import flight_agent
from typing import Literal
# # ---- Define shared state ----
# class State(MessagesState):
#     llm_output: str
#     decision: str

# # ---- Wrappers for agents so they store output in llm_output ----
# def run_flight_agent(state: State) -> State:
#     resp = flight_agent.invoke(state)
#     return {"llm_output": str(resp)}

# def run_hotel_agent(state: State) -> State:
#     resp = hotel_agent.invoke(state)
#     return {"llm_output": str(resp)}

# def run_activity_agent(state: State) -> State:
#     resp = activity_agent.invoke(state)
#     return {"llm_output": str(resp)}


# ---- Factory for approval nodes ----
def make_human_approval(
    approve_dest: str,
    reject_dest: str,
    question: str = "Do you approve this output?",
    field: str = "llm_output",
) -> Callable:
    def human_approval(state: dict) -> Command:
        decision = interrupt({"question": question, field: state.get(field, "")})

        if decision == "approve":
            return Command(goto=approve_dest, update={"decision": "approved"})
        else:
            return Command(goto=reject_dest, update={"decision": "rejected"})

    return human_approval


# # ---- Approved marker nodes ----
# def flight_approved(state: dict) -> dict:
#     return {"flights_approved": True}

# def hotel_approved(state: dict) -> dict:
#     return {"hotels_approved": True}

# def activities_approved(state: dict) -> dict:
#     return {"activities_approved": True}

# # ---- Build graph ----
# builder = StateGraph(State)

# # Core agent wrappers
# builder.add_node("flight_agent", run_flight_agent)
# builder.add_node("hotel_agent", run_hotel_agent)
# builder.add_node("activity_agent", run_activity_agent)

# # Approval steps
# builder.add_node("approve_flights",
#     make_human_approval(
#         approve_dest="flights_approved",
#         reject_dest="flight_agent",
#         question="Do you approve these flights?",
#         field="llm_output"
#     )
# )
# builder.add_node("approve_hotels",
#     make_human_approval(
#         approve_dest="hotels_approved",
#         reject_dest="hotel_agent",
#         question="Do you approve this hotel?",
#         field="llm_output"
#     )
# )
# builder.add_node("approve_activities",
#     make_human_approval(
#         approve_dest="activities_approved",
#         reject_dest="activity_agent",
#         question="Do you approve these activities?",
#         field="llm_output"
#     )
# )

# # Approved markers
# builder.add_node("flights_approved", flight_approved)
# builder.add_node("hotels_approved", hotel_approved)
# builder.add_node("activities_approved", activities_approved)

# # ---- Flights flow ----
# builder.set_entry_point("flight_agent")
# builder.add_edge("flight_agent", "approve_flights")
# builder.add_edge("flights_approved", "hotel_agent")

# # ---- Hotels flow ----
# builder.add_edge("hotel_agent", "approve_hotels")
# builder.add_edge("hotels_approved", "activity_agent")

# # ---- Activities flow ----
# builder.add_edge("activity_agent", "approve_activities")

# # End when all activities approved
# builder.add_edge("activities_approved", END)

# graph = builder.compile()


# Define the shared graph state
class State(MessagesState):
    llm_output: str
    decision: str


# Human approval node
def human_approval(state: State) -> Command[Literal["approved_path", "rejected_path"]]:
    input = interrupt(
        {
            "question": "Do you approve the following output?",
            # field to show to the human
            "messages": state["messages"],
        }
    )

    messages = state["messages"]

    if input == "approve":
        return Command(goto="approved_path", update={"input": "approved"})
    else:
        return Command(
            goto="rejected_path",
            update={"input": "rejected", "messages": messages + [input]},
        )


# Next steps after approval
def approved_node(state: State) -> State:
    print("✅ Approved path taken.")
    return state


# Alternative path after rejection
def rejected_node(state: State) -> State:
    print("❌ Rejected path taken.")
    return state


# Build the graph
builder = StateGraph(State)
builder.add_node("flight_agent", flight_agent)
builder.add_node("human_approval", human_approval)
builder.add_node("approved_path", approved_node)
builder.add_node("rejected_path", rejected_node)

builder.set_entry_point("flight_agent")
builder.add_edge("flight_agent", "human_approval")
builder.add_edge("approved_path", END)
builder.add_edge("rejected_path", "flight_agent")

# checkpointer = InMemorySaver()
graph = builder.compile()

# # Run until interrupt
# config = {"configurable": {"thread_id": uuid.uuid4()}}
# result = graph.invoke({}, config=config)
# print(result["__interrupt__"])
# # Output:
# # Interrupt(value={'question': 'Do you approve the following output?', 'llm_output': 'This is the generated output.'}, ...)

# # Simulate resuming with human input
# # To test rejection, replace resume="approve" with resume="reject"
# final_result = graph.invoke(Command(resume="approve"), config=config)
# print(final_result)
