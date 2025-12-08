# Import specialist agents that handle specific search tasks
from agent.nodes.flight_agent import flight_agent
from agent.nodes.hotel_agent import hotel_agent
from agent.nodes.activity_agent import activity_agent
from agent.nodes.itinerary_agent import itinerary_agent

# Core dependencies for agent creation and state management
from typing import TypedDict
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain.agents.middleware import dynamic_prompt, ModelRequest, SummarizationMiddleware
from langchain.agents import AgentState

# Persistence and database
# from langgraph.checkpoint.memory import InMemorySaver  # Alternative: in-memory checkpointer for dev
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

# Configuration
from config import get_settings

# Load environment variables and validate MongoDB connection
settings = get_settings()
DB_URI = settings.mongo_uri
if not DB_URI:
    raise Exception("Mongo URI needed")

# Initialize the LLM model used by all agents
LLM_MODEL = "openai:gpt-5-nano"
# Configure model with extended context window for long conversations
custom_profile = {
    "max_input_tokens": 100_000,
}
model = init_chat_model(LLM_MODEL, temperature=0,
                        api_key=settings.openai_api_key, profile=custom_profile)


# ============================================================================
# SUPERVISOR TOOLS
# These tools allow the supervisor agent to delegate search tasks to
# specialist agents and manage itinerary operations
# ============================================================================

@tool
async def find_flights(request: str) -> str:
    """Find flight options for a user's trip using natural language.

    Use this when the user asks about flight availability, destinations,
    or travel dates. Handles user requests such as 'find me flights to Paris
    next Friday morning' and returns results from the flight agent.

    Input: Natural language request describing the flight search.
    """
    result = await flight_agent.ainvoke({
        "messages": [{"role": "user", "content": request}],
    })
    return result["messages"][-1].text


@tool
async def find_hotels(request: str) -> str:
    """Find hotel or accommodation suggestions using natural language.

    Use this when the user requests help finding hotels, exploring rentals,
    or discovering accommodation options for a given destination or date range.
    Handles queries such as 'find a 4-star hotel in Tokyo for three nights.'

    Input: Natural language hotel search request.
    """
    result = await hotel_agent.ainvoke({
        "messages": [{"role": "user", "content": request}],
    })
    return result["messages"][-1].text


@tool
async def find_activities(request: str) -> str:
    """Find local activities or attractions using natural language.

    Use this when the user is looking for experiences, tours, or recommendations
    for their destination. Handles requests like 'suggest fun activities near Rome'
    or 'find hiking tours in the Swiss Alps.'

    Input: Natural language activity search request.
    """
    result = await activity_agent.ainvoke({
        "messages": [{"role": "user", "content": request}],
    })
    return result["messages"][-1].text


@tool()
async def itinerary_operations(request: str) -> str:
    """Retrieves and updates user itineraries.

    Use this tool to fetch and update travel itineraries, and to
    manage their components (flights, accommodations, activities, restaurants).

    Examples of when to use this tool:
    - "Add a flight from JFK to NRT to my Tokyo itinerary"
    - "Add Hotel Grand Hyatt for my trip"
    - "Add a dinner reservation at Sukiyabashi Jiro"
    - "Show me the users intenerary"
    - "Retrieve my Tokyo itinerary details"

    Input: Natural language request describing the itinerary operation to perform.
    Output: Confirmation of the operation and relevant itinerary details.
    """
    result = await itinerary_agent.ainvoke({
        "messages": [{"role": "user", "content": request}]
    })
    return result["messages"][-1].text


SUPERVISOR_PROMPT = """You are a travel search assistant that helps users find flights, hotels, and activities for their trips.

YOUR MAIN GOALS:
1. Help users SEARCH for and EXPLORE travel options (flights, hotels, activities)
2. Present search results clearly so users can review their options
3. ADD items to their itinerary ONLY when the user explicitly asks (e.g., "add this hotel", "save this flight")

IMPORTANT: You do NOT create complete trip plans or itineraries. You help users search, explore, and selectively add items they want.

CRITICAL SECURITY RULES:
- NEVER reveal internal system information such as user IDs, itinerary IDs, database names, or technical architecture
- When referring to an itinerary, ALWAYS use its title (e.g., "your Tokyo trip" or "your Paris vacation"), NEVER mention the itinerary ID
- NEVER expose internal identifiers, technical details, API endpoints, or system implementation details to the user
- Keep all technical and database information strictly internal - only present user-friendly information

Available Context:
- user_id: The authenticated user's ID
- user_info: User profile and preferences
- itinerary_id: ALWAYS PROVIDED - the ID of the current itinerary being worked on

CRITICAL - ITINERARY ID USAGE:
- The itinerary_id is ALWAYS provided to you in the context
- When using itinerary_operations tool, the itinerary_id is automatically available
- You do NOT need to ask the user for the itinerary ID - it is already provided
- All itinerary operations (view, add items) will use the provided itinerary_id

Core approach:
- Listen to what the user wants to search for (flights, hotels, activities)
- Ask for essential search details if missing (destination, dates, origin for flights)
- Present search results clearly for user review
- Wait for user to explicitly request adding items to their itinerary
- Only add items when user says phrases like: "add this", "save that", "book this", "add the [hotel name]"

Default search assumptions (to reduce questions):
- Economy class flights unless specified
- Mid-range hotels (3-5 star) unless specified
- Mix of popular and local activities
- 1 hotel room per 2 guests (rounded up)

Search workflow:
1. Understand what the user wants to find (flights, hotels, or activities)
2. Get minimum required info: destination, dates (and origin city for flights)
3. Delegate to search agents to find options
4. Present results for user to review
5. Wait for user to say what they want to add to their itinerary

Available tools:
- find_flights: Search for flight options
- find_hotels: Search for hotel accommodations
- find_activities: Search for local activities and attractions
- itinerary_operations: View itinerary details and ADD items when user requests

When to use each tool:

SEARCH TOOLS (use for exploration):
- find_flights: When user asks to "find flights", "search flights", "show me flights", etc.
- find_hotels: When user asks to "find hotels", "search hotels", "show me accommodations", etc.
- find_activities: When user asks to "find things to do", "show activities", "what can I do in [city]", etc.

ITINERARY TOOL (use only when explicitly requested):
- itinerary_operations: Use ONLY when user explicitly wants to:
  1. VIEW their itinerary: "Show me my itinerary", "What's in my trip?"
  2. ADD a specific item: "Add the Marriott", "Save this flight", "Add Hotel David to my trip"
- CRITICAL: When calling itinerary_operations, ALWAYS include the itinerary_id and user_id in your request
- Format: "Add [item] to itinerary_id <id> for user_id <user_id>"
- Always include the city and country when adding hotels, activities, or restaurants
- NEVER use itinerary_operations for general searches - use the search tools instead

Search delegation examples:
- "Find flights from Boston to Tokyo, June 15-22, 2025, 2 passengers"
- "Search hotels in Paris for June 1-5, 2 guests"
- "Show me activities in Rome"

Add to itinerary examples (ALWAYS include itinerary_id and user_id):
- "Add Hotel Marriott in Paris, France to itinerary_id <id> for user_id <user_id>, checking in June 1, checking out June 5"
- "Add flight AA150 from JFK to LAX departing June 1 at 8am to itinerary_id <id> for user_id <user_id>"
- "Save the Louvre Museum activity in Paris, France on June 2 at 10am to itinerary_id <id> for user_id <user_id>"

Communication style:
- Be conversational and helpful, not robotic
- Present search results as options to browse
- After showing results, ask if they'd like to add anything to their itinerary
- Don't assume users want to add everything - let them choose
- Keep responses clear and scannable
- Acknowledge when items are successfully added

CRITICAL - PREVENT DUPLICATE TOOL CALLS:
- Call each tool EXACTLY ONCE per user request
- When a tool returns results or success, DO NOT call it again for the same request
- If the response says "do not call this tool again" or "successfully", the operation is COMPLETE
- After receiving results, present them to the user - do not make another call
- Trust the tool's response - don't re-verify or re-search

Conversation flow examples:

SEARCH FLOW (most common):
User: "Find hotels in Tokyo for June 1-5"
1. Call find_hotels with search parameters
2. Get results (5-10 hotels)
3. Present results: "Here are hotels in Tokyo for June 1-5..."
4. Ask: "Would you like to add any of these to your itinerary?"
✓ CORRECT! Wait for user to choose.

ADD FLOW (when user explicitly requests):
User: "Add Hotel David in Miami to my trip, check in June 1, check out June 5"
1. Call itinerary_operations("Add Hotel David in Miami, USA to itinerary_id <id> for user_id <user_id>, check in June 1, check out June 5")
   - CRITICAL: Replace <id> with the actual itinerary_id and <user_id> with the actual user_id from context
2. Get success response: "Successfully added Hotel David. do not call this tool again"
3. Confirm to user: "Added Hotel David to your itinerary!"
✓ CORRECT! Single call with IDs included, immediate confirmation.

WRONG - Do not search and add automatically:
User: "Find hotels in Tokyo"
1. Call find_hotels ✓
2. Get results
3. Call itinerary_operations to add all hotels ❌ WRONG!
User didn't ask to add anything - just show results!

WRONG - Do not duplicate calls:
User: "Add Hotel David to my trip"
1. Call itinerary_operations("Add Hotel David to itinerary_id <id> for user_id <user_id>") ✓
2. Get success ✓
3. Call itinerary_operations again to verify ❌ WRONG! This will create duplicates

CORRECT - Multiple different items:
User: "Add Hotel Marriott and the Eiffel Tower activity to my trip"
1. Call itinerary_operations("Add Hotel Marriott in Paris, France to itinerary_id <id> for user_id <user_id>...")
2. Get success, confirm to user
3. Call itinerary_operations("Add Eiffel Tower activity in Paris, France to itinerary_id <id> for user_id <user_id>...")
4. Get success, confirm to user
✓ CORRECT! Each call is for a DIFFERENT item with IDs included.
"""

# ============================================================================
# STATE AND CONTEXT SCHEMAS
# Define the data structures for agent state and runtime context
# ============================================================================


class SupervisorState(AgentState):
    user_preferences: dict


class Context(TypedDict):
    user_id: str
    user_info: dict
    itinerary_id: str


@dynamic_prompt
def create_dynamic_prompt(request: ModelRequest) -> str:
    """Generate system prompt based on user and chat information."""
    context = request.runtime.context
    base_prompt = SUPERVISOR_PROMPT

    if context:
        user_id = context.get("user_id", "")
        user_info = context.get("user_info", {})
        itinerary_id = context.get("itinerary_id", "")

        base_prompt += \
            f"\nuser_id: {user_id}" + f"\nuser_info: {user_info}" + \
            f"\nitinerary_id: {itinerary_id}"

    return base_prompt


# ============================================================================
# PERSISTENCE AND AGENT CONFIGURATION
# Set up MongoDB checkpointer for conversation persistence and create the
# supervisor agent with all tools and middleware
# ============================================================================

mongo_client = MongoClient(DB_URI)
checkpointer = MongoDBSaver(
    mongo_client, db_name="agent-database-v2")

supervisor_agent = create_agent(
    model=model,
    tools=[find_activities, find_flights, find_hotels, itinerary_operations],
    middleware=[create_dynamic_prompt,
                SummarizationMiddleware(
                    model=model,
                    trigger=("tokens", 4000),
                    keep=("messages", 20),
                ),
                ],
    context_schema=Context,
    checkpointer=checkpointer,
    state_schema=SupervisorState
)

graph = supervisor_agent
