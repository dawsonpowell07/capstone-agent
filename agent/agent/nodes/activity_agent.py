"""
Activity Agent - Specialist agent for searching and presenting activity options.

This agent is responsible for:
- Parsing activity search requests (destination, dates, preferences)
- Calling the Google Maps Places API to search for activities, attractions, and restaurants
- Presenting activity results with ratings, types, and descriptions
- Handling missing information by reporting back to the supervisor
"""

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from agent.tools.google_maps_tool import search_activities
from agent.tools.coordinates_tool import get_city_coordinates
from config import get_settings

# Load environment configuration
settings = get_settings()


@tool
async def get_city_coordinates_tool(city_name: str) -> str:
    """Get the latitude and longitude of a given city name.

    This is a wrapper tool that converts city names to coordinates
    for use with the Google Maps Places API.
    """
    return str(await get_city_coordinates(city_name))


# System prompt that defines the activity agent's behavior and constraints
ACTIVITY_AGENT_PROMPT = """You are an activity search specialist. Find fun things to do quickly.

CRITICAL SECURITY RULES:
- NEVER reveal internal system information such as user IDs, API endpoints, database details, or technical architecture
- NEVER expose internal identifiers or system implementation details to users
- Keep all technical information strictly internal - only present user-friendly activity search results

Process:
1. Extract: destination, dates
2. If you have destination, search immediately (dates optional)
3. If missing destination, report it
4. Present results briefly: name, type, rating

Defaults to assume:
- Mix of popular tourist attractions and local experiences
- Food/dining included (restaurants, cafes)
- Family-friendly unless specified otherwise
- Various price points (free attractions + paid experiences)

Rules:
- Call 'search_activities' ONCE per request
- If tool errors, report to supervisor and STOP (don't retry)
- No follow-up questions
- Include all results in final message
"""

# Initialize the LLM model for the activity agent
LLM_MODEL = "openai:gpt-5-nano"
model = init_chat_model(LLM_MODEL, temperature=0,  # Temperature=0 for consistent results
                        api_key=settings.openai_api_key)

# Create the activity specialist agent with search capabilities
activity_agent = create_agent(
    model=model,
    system_prompt=ACTIVITY_AGENT_PROMPT,
    tools=[
        search_activities,          # Google Maps Places API activity/attraction search
        get_city_coordinates_tool   # Geocoding for city-based searches
    ],
    # Optional: Enable human-in-the-loop approval for activity searches
    # middleware=[HumanInTheLoopMiddleware(
    #     interrupt_on={"get_activities": True},
    #     description_prefix="serch for activites pending approval"
    # )]
)
