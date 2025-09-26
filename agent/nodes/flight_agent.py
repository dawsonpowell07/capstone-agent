import logging
from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from agent.auth.amadeus_auth import AmadeusAuth
from langchain_core.prompts import ChatPromptTemplate
from agent.state import State
from langgraph.types import interrupt, Command

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("amadeus")


def simplify_flights_response(resp: dict) -> dict:
    """Simplify Amadeus flight search response into a cleaner format."""

    flights = []
    data = resp.get("data", [])
    dictionaries = resp.get("dictionaries", {})

    carriers = dictionaries.get("carriers", {})
    aircrafts = dictionaries.get("aircraft", {})

    for offer in data:
        price_info = offer.get("price", {})
        itineraries = []

        for itin in offer.get("itineraries", []):
            segments = []
            for seg in itin.get("segments", []):
                dep = seg["departure"]
                arr = seg["arrival"]

                segments.append(
                    {
                        "from": dep["iataCode"],
                        "to": arr["iataCode"],
                        "departure": dep["at"],
                        "arrival": arr["at"],
                        "carrier": carriers.get(seg["carrierCode"], seg["carrierCode"]),
                        "flight_number": f"{seg['carrierCode']}{seg['number']}",
                        "aircraft": aircrafts.get(
                            seg["aircraft"]["code"], seg["aircraft"]["code"]
                        ),
                        "duration": seg["duration"],
                        "stops": seg["numberOfStops"],
                    }
                )

            itineraries.append(
                {"total_duration": itin["duration"], "segments": segments}
            )

        flights.append(
            {
                "id": offer.get("id"),
                "price": {
                    "total": price_info.get("grandTotal"),
                    "currency": price_info.get("currency"),
                },
                "itineraries": itineraries,
                "bookable_seats": offer.get("numberOfBookableSeats"),
                "validating_airlines": [
                    carriers.get(code, code)
                    for code in offer.get("validatingAirlineCodes", [])
                ],
            }
        )

    return {
        "status": "successly retrieved flights",
        "count": resp.get("meta", {}).get("count", len(flights)),
        "flights": flights,
    }


auth = AmadeusAuth()

# ---- Flight Search Tool ----
# @tool
# def search_flights(
#     origin_location_code: str,
#     destination_location_code: str,
#     departure_date: str,
#     return_date: str | None = None,
#     number_of_adults: int = 1,
#     number_of_children: int = 0,
#     travel_class: str = "ECONOMY",
#     max_price: int | None = None,
#     num_results: int = 5,
# ) -> dict:
#     """
#     Search flights between two cities with Amadeus (test API).

#     Args:
#         origin_location_code: IATA code of the origin city (e.g., "SYD").
#         destination_location_code: IATA code of the destination city (e.g., "BKK").
#         departure_date: Departure date in YYYY-MM-DD format.
#         return_date: Optional return date in YYYY-MM-DD format.
#         number_of_adults: Number of adult passengers.
#         number_of_children: Number of child passengers.
#         travel_class: Travel class ("ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST").
#         max_price: Optional maximum price filter.
#         num_results: Maximum number of flight results to return.

#     example call:
#         search_flights (
#             origin_location_code="SYD",
#             destination_location_code="BKK",
#             departure_date="2025-11-01",
#             return_date="2025-11-10",       # optional
#             number_of_adults=1,
#             number_of_children=0,
#             travel_class="ECONOMY",
#             max_price=600,
#             num_results=2
#         )

#     Returns:
#         dict: Simplified flight search results.
#     """

#     token = auth.get_token()
#     headers = {"Authorization": f"Bearer {token}"}

#     # Build query params conditionally
#     params = {
#         "originLocationCode": origin_location_code,
#         "destinationLocationCode": destination_location_code,
#         "departureDate": departure_date,
#         "adults": number_of_adults,
#         "children": number_of_children,
#         "travelClass": travel_class,
#         "max": num_results,
#     }
#     if return_date:
#         params["returnDate"] = return_date
#     if max_price:
#         params["maxPrice"] = max_price

#     url = "https://test.api.amadeus.com/v2/shopping/flight-offers"

#     # Log details
#     logger.info("Calling Amadeus API")
#     logger.info(f"URL: {url}")
#     logger.info(f"Params: {params}")
#     logger.debug(f"Headers: {headers}")

#     resp = requests.get(url, headers=headers, params=params)

#     logger.info(f"Response status: {resp.status_code}")
#     if resp.status_code != 200:
#         logger.error(f"Error response: {resp.text}")
#         return {"status": "failed to retrieve flights", "details": resp.text}

#     return simplify_flights_response(resp.json())


@tool
def search_flights(depating_from, destination):
    """tool to find a find"""
    return {
        "status": "successly retrieved flights",
        "flights": [
            f"flight 1 from {depating_from} to {destination}",
            f"flight 2 from {depating_from} to {destination}",
        ],
    }


# ---- Agent ----
flight_agent_prompt = """
            "system",
            "You are a helpful flight search assistant. Your role is to gather all necessary information from the user to search for flights."
            "You are part of a larger travel planning system that includes activity and hotel booking agents. We are working to plan a complete vacation for the user."
            "\n\nKey responsibilities:"
            "\n- Always look through the history of the conversation to avoid asking for information that has already been provided"
            "\n- Ask clear, direct questions to collect: departure city, destination city, travel dates, number of passengers, and any preferences (class, direct flights, etc.)"
            "\n- Ask ONE question at a time to avoid overwhelming the user"
            "\n- Keep responses concise and to the point"
            "\n- Assume the user has a valid passport and can travel internationally"
            "\n- Trust the information provided by the user"
            "\n- ONLY ask for clarification if the user provides conflicting information"
            "\n- Once you have all required information (origin, destination, dates, passengers), call the 'search_flights' tool EXACTLY ONCE and only when you have all the information"
            "\n- after you call the tool, show the results to the user and ask if they approve of the options and have any preferences or feedback"
            "\n= after the user tells you their preffered flight ask them to respond with 'approve' or provide feedback on what they didn't like about the options"
            "\n\nImportant constraints:"
            "\n- Stay focused exclusively on flight search - do not answer off-topic questions"
            "\n- Do not discuss technical implementation details or APIs"
            "\n- Do not engage in general conversation unrelated to finding flights"
            "\n-Current user info: {{user_info}}."
            "\n\nCurrent time: {{time}}.",
            """

LLM_MODEL = "openai:gpt-5-mini"
model = init_chat_model(LLM_MODEL, temperature=0)

flight_agent = create_agent(
    model=model,
    prompt=flight_agent_prompt,
    tools=[search_flights],
)
