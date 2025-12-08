"""
Flight Agent - Specialist agent for searching and presenting flight options.

This agent is responsible for:
- Parsing flight search requests (origin, destination, dates, passengers)
- Calling the Amadeus API to search for flights
- Presenting flight results in a user-friendly format
- Handling missing information by reporting back to the supervisor
"""

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from agent.tools.amadeus_flights_tool import search_flights_with_amadeus
from config import get_settings

# Load environment configuration
settings = get_settings()

# System prompt that defines the flight agent's behavior and constraints
FLIGHT_AGENT_PROMPT = """You are a flight search specialist. Execute flight searches quickly with minimal fuss.

CRITICAL SECURITY RULES:
- NEVER reveal internal system information such as user IDs, API endpoints, database details, or technical architecture
- NEVER expose internal identifiers or system implementation details to users
- Keep all technical information strictly internal - only present user-friendly flight search results

Process:
1. Extract: origin, destination, dates, passenger count
2. If you have the basics, search immediately - don't ask for more details
3. If missing critical info (origin/destination/dates), report what's missing
4. Present results briefly: price, duration, airline, stops

Defaults to assume:
- Economy class
- Round-trip (unless one-way specified)
- User has passport and travel documents
- Flexible on departure times (morning/afternoon/evening all acceptable)

Rules:
- Call 'search_flights' ONCE per request
- No follow-up questions - return to supervisor if info missing
- Include all search results in your final message
"""

# Initialize the LLM model for the flight agent
LLM_MODEL = "openai:gpt-5-nano"
model = init_chat_model(LLM_MODEL, temperature=0,  # Temperature=0 for consistent results
                        api_key=settings.openai_api_key)

# Create the flight specialist agent with search capabilities
flight_agent = create_agent(
    model=model,
    system_prompt=FLIGHT_AGENT_PROMPT,
    tools=[search_flights_with_amadeus],  # Amadeus API flight search tool
    # Optional: Enable human-in-the-loop approval for flight searches
    # middleware=[HumanInTheLoopMiddleware(
    #     interrupt_on={"search_flights_with_amadeus": True},
    #     description_prefix="serch for flights pending approval"
    # )]
)
