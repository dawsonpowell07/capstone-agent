from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig


@tool
def get_activities(config: RunnableConfig) -> str:
    """Retrieve activities near the vacation area (dummy)."""
    return "Eiffel Tower tour, Louvre Museum tickets, Seine River cruise."


model = init_chat_model("openai:gpt-5-nano", temperature=0)

# Activity Agent
activity_agent = create_agent(
    model=model,
    prompt="You are a helpful activity assistant. Use tools to find fun activities around the vacation area.",
    tools=[get_activities],
)
