import os
import time
import requests
import logging
from datetime import datetime
from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from agent.auth.amadeus_auth import AmadeusAuth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
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

                segments.append({
                    "from": dep["iataCode"],
                    "to": arr["iataCode"],
                    "departure": dep["at"],
                    "arrival": arr["at"],
                    "carrier": carriers.get(seg["carrierCode"], seg["carrierCode"]),
                    "flight_number": f"{seg['carrierCode']}{seg['number']}",
                    "aircraft": aircrafts.get(seg["aircraft"]["code"], seg["aircraft"]["code"]),
                    "duration": seg["duration"],
                    "stops": seg["numberOfStops"],
                })

            itineraries.append({
                "total_duration": itin["duration"],
                "segments": segments
            })

        flights.append({
            "id": offer.get("id"),
            "price": {
                "total": price_info.get("grandTotal"),
                "currency": price_info.get("currency"),
            },
            "itineraries": itineraries,
            "bookable_seats": offer.get("numberOfBookableSeats"),
            "validating_airlines": [
                carriers.get(code, code) for code in offer.get("validatingAirlineCodes", [])
            ]
        })

    return {
        "status": "successly retrieved flights",
        "count": resp.get("meta", {}).get("count", len(flights)),
        "flights": flights
    }

auth = AmadeusAuth()

# ---- Flight Search Tool ----
def search_flights(
    origin_location_code: str,
    destination_location_code: str,
    departure_date: str,
    return_date: str | None = None,
    number_of_adults: int = 1,
    number_of_children: int = 0,
    travel_class: str = "ECONOMY",
    max_price: int | None = None,
    num_results: int = 5,
) -> dict:
    """
    Search flights between two cities with Amadeus (test API).
    
    Args:
        origin_location_code: IATA code of the origin city (e.g., "SYD").
        destination_location_code: IATA code of the destination city (e.g., "BKK").
        departure_date: Departure date in YYYY-MM-DD format.
        return_date: Optional return date in YYYY-MM-DD format.
        number_of_adults: Number of adult passengers.
        number_of_children: Number of child passengers.
        travel_class: Travel class ("ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST").
        max_price: Optional maximum price filter.
        num_results: Maximum number of flight results to return.
        
    example call:
        search_flights (
            origin_location_code="SYD",
            destination_location_code="BKK",
            departure_date="2025-11-01",
            return_date="2025-11-10",       # optional
            number_of_adults=1,
            number_of_children=0,
            travel_class="ECONOMY",
            max_price=600,
            num_results=2
        )
        
    Returns:
        dict: Simplified flight search results.
    """

    token = auth.get_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Build query params conditionally
    params = {
        "originLocationCode": origin_location_code,
        "destinationLocationCode": destination_location_code,
        "departureDate": departure_date,
        "adults": number_of_adults,
        "children": number_of_children,
        "travelClass": travel_class,
        "max": num_results,
    }
    if return_date:
        params["returnDate"] = return_date
    if max_price:
        params["maxPrice"] = max_price

    url = "https://test.api.amadeus.com/v2/shopping/flight-offers"

    # Log details
    logger.info("Calling Amadeus API")
    logger.info(f"URL: {url}")
    logger.info(f"Params: {params}")
    logger.debug(f"Headers: {headers}")

    resp = requests.get(url, headers=headers, params=params)

    logger.info(f"Response status: {resp.status_code}")
    if resp.status_code != 200:
        logger.error(f"Error response: {resp.text}")
        return {"status": "failed to retrieve flights", "details": resp.text}

    return simplify_flights_response(resp.json())


# ---- Agent ----
model = init_chat_model("openai:gpt-5-nano", temperature=0)

flight_agent = create_agent(
    model=model,
    prompt="""You are a helpful flight assistant. 
    Keep asking questions until you have all the information needed to search for flights.
    Use tools to find flights to and 
    from the vacation destination. ONLY call the 'search_flights' tool a single time.""",
    tools=[search_flights],
)
