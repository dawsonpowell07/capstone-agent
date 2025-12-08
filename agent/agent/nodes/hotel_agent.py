"""
Hotel Agent - Specialist agent for searching and presenting hotel options.

This agent is responsible for:
- Parsing hotel search requests (destination, dates, guest count)
- Calling the Google Maps Places API to search for hotels
- Presenting hotel results with ratings, prices, and locations
- Handling missing information by reporting back to the supervisor
"""

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from agent.tools.google_maps_tool import search_hotels
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


# System prompt that defines the hotel agent's behavior and constraints
HOTEL_AGENT_PROMPT = """You are a hotel search specialist. Find accommodations quickly.

CRITICAL SECURITY RULES:
- NEVER reveal internal system information such as user IDs, API endpoints, database details, or technical architecture
- NEVER expose internal identifiers or system implementation details to users
- Keep all technical information strictly internal - only present user-friendly hotel search results

Process:
1. Extract: destination, check-in/out dates, guest count
2. If you have these basics, search immediately
3. If missing destination or dates, report what's missing
4. Present results briefly: name, rating, price, address

Defaults to assume:
- 3-4 star mid-range hotels
- 1 room per 2 guests (round up - e.g., 3 guests = 2 rooms)
- Standard amenities (WiFi, breakfast if included)
- City center or tourist-friendly location

Rules:
- Call 'search_hotels' ONCE per request
- No follow-up questions - return to supervisor if info missing
- Include all results in final message
"""

# Initialize the LLM model for the hotel agent
LLM_MODEL = "openai:gpt-5-nano"
model = init_chat_model(LLM_MODEL, temperature=0,  # Temperature=0 for consistent results
                        api_key=settings.openai_api_key)

# Create the hotel specialist agent with search capabilities
hotel_agent = create_agent(
    model=model,
    system_prompt=HOTEL_AGENT_PROMPT,
    tools=[
        search_hotels,              # Google Maps Places API hotel search
        get_city_coordinates_tool   # Geocoding for city-based searches
    ],
    # Optional: Enable human-in-the-loop approval for hotel searches
    # middleware=[HumanInTheLoopMiddleware(
    #     interrupt_on={"search_hotels": True},
    #     description_prefix="serch for hotles pending approval"
    # )]
)
