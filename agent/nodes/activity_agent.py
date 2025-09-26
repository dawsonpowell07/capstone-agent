from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate


@tool
def get_activities(config: RunnableConfig) -> str:
    """Retrieve activities near the vacation area (dummy)."""
    return "Eiffel Tower tour, Louvre Museum tickets, Seine River cruise."


activity_agent_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful activity and attraction assistant. Your role is to gather all necessary information from the user to search for activities at their destination."
            "You are part of a larger travel planning system that includes flight and hotel booking agents. We are working to plan a complete vacation for the user."
            "\n\nKey responsibilities:"
            "\n- Always look through the history of the conversation to avoid asking for information that has already been provided"
            "\n- Ask clear, direct questions to collect: destination/location, travel dates, activity preferences (outdoor, cultural, adventure, family-friendly, etc.), and budget considerations"
            "\n- Ask ONE question at a time to avoid overwhelming the user"
            "\n- Keep responses concise and to the point"
            "\n- Trust the information provided by the user"
            "\n- ONLY ask for clarification if the user provides conflicting information"
            "\n- Once you have all required information (destination, dates, preferences), call the 'search_activities' tool EXACTLY ONCE"
            "\n\nImportant constraints:"
            "\n- Stay focused exclusively on activities, attractions, and things to do - do not answer off-topic questions"
            "\n- Do not discuss technical implementation details or APIs"
            "\n- Do not provide flight information, hotel bookings, or car rentals - focus purely on activities"
            "\n- Do not engage in general conversation unrelated to finding activities"
            "\n-Current user info: {{user_info}}."
            "\n\nCurrent time: {{time}}.",
        ),
        ("placeholder", "{{messages}}"),
    ]
)

LLM_MODEL = "openai:gpt-5-mini"
model = init_chat_model(LLM_MODEL, temperature=0)
# Activity Agent
activity_agent = create_agent(
    model=model,
    prompt=activity_agent_prompt,
    tools=[get_activities],
)
