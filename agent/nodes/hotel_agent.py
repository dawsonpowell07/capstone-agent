from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig


@tool
def get_hotels(config: RunnableConfig) -> str:
    """Retrieve hotels or rentals at the destination (dummy)."""
    return "Hotel: Le Meurice, Paris. Rate: $450/night."


model = init_chat_model("openai:gpt-5-nano", temperature=0)


# Hotel Agent
hotel_agent = create_agent(
    model=model,
    prompt="You are a helpful hotel assistant. Use tools to find hotels, condos, or rentals at the vacation destination.",
    tools=[get_hotels],
)
