from langgraph.graph import MessagesState
from typing import Annotated
import operator
class State(MessagesState):
    llm_output: str
    flight_decision: str
    hotel_decision: str
    activity_decision: str
    user_info: dict
    user_flight_feedback: Annotated[list, operator.add]
