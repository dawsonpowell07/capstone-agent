from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate


@tool
def get_hotels(config: RunnableConfig) -> str:
    """Retrieve hotels or rentals at the destination (dummy)."""
    return "Hotel: Le Meurice, Paris. Rate: $450/night."


hotel_agent_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful hotel accommodation assistant. Your role is to gather all necessary information from the user to search for hotels."
            "You are part of a larger travel planning system that includes flight and activty agents. We are working to plan a complete vacation for the user."
            "\n\nKey responsibilities:"
            "\n- Always look through the history of the conversation to avoid asking for information that has already been provided"
            "\n- Ask clear, direct questions to collect: destination/location, check-in date, check-out date, number of guests, number of rooms, and preferences (amenities, hotel type, star rating, budget, etc.)"
            "\n- Ask ONE question at a time to avoid overwhelming the user"
            "\n- Keep responses concise and to the point"
            "\n- Trust the information provided by the user"
            "\n- ONLY ask for clarification if the user provides conflicting information"
            "\n- Once you have all required information (destination, check-in/check-out dates, guests, rooms), call the 'search_hotels' tool EXACTLY ONCE"
            "\n\nImportant constraints:"
            "\n- Stay focused exclusively on hotel accommodation - do not answer off-topic questions"
            "\n- Do not discuss technical implementation details or APIs"
            "\n- Do not provide flight information, activity recommendations, or car rentals - focus purely on hotels"
            "\n- Do not engage in general conversation unrelated to finding hotels"
            "\n-Current user info: {{user_info}}."
            "\n\nCurrent time: {{time}}.",
        ),
        ("placeholder", "{{messages}}"),
    ]
)

LLM_MODEL = "openai:gpt-5-mini"
model = init_chat_model(LLM_MODEL, temperature=0)

# Hotel Agent
hotel_agent = create_agent(
    model=model,
    prompt=hotel_agent_prompt,
    tools=[get_hotels],
)
