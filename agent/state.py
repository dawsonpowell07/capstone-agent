from langgraph.graph import MessagesState
from typing import Any


class State(MessagesState):
    user_info: dict[str, Any]
