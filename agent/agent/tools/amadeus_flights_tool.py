"""
Amadeus Flight Search Tool - Search for flights between destinations.

This tool uses the Amadeus Travel API to search for flight offers between two cities.
It handles authentication, parameter validation, error responses, and transforms
the complex Amadeus response into a simplified format.
"""

from agent.auth.amadeus_auth import AmadeusAuth
from langchain_core.tools import tool
import httpx


def simplify_flights_response(resp: dict) -> dict:
    """Transform Amadeus flight API response into a simplified, agent-friendly format.

    Extracts key information like price, itineraries, segments, and carrier names
    from the raw Amadeus response and dictionaries.
    """
    flights = []
    data = resp.get("data", [])
    # Dictionaries contain human-readable names for carrier codes, aircraft types, etc.
    dictionaries = resp.get("dictionaries", {})

    carriers = dictionaries.get("carriers", {})
    aircrafts = dictionaries.get("aircraft", {})

    # Process each flight offer
    for offer in data:
        price_info = offer.get("price", {})
        itineraries = []

        # Each flight offer may have multiple itineraries (outbound, return)
        for itin in offer.get("itineraries", []):
            segments = []
            # Each itinerary contains segments (individual flights, including connections)
            for seg in itin.get("segments", []):
                dep = seg["departure"]
                arr = seg["arrival"]

                # Build simplified segment with human-readable carrier names
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
        "message": "successfully got flights. do not call this tool again."
    }


# Initialize Amadeus authentication handler
auth = AmadeusAuth()


@tool
async def search_flights_with_amadeus(
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
    # Get OAuth2 token for Amadeus API authentication
    token = await auth.get_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Build query parameters for flight search
    params = {
        "originLocationCode": origin_location_code,
        "destinationLocationCode": destination_location_code,
        "departureDate": departure_date,
        "adults": number_of_adults,
        "children": number_of_children,
        "travelClass": travel_class,
        "max": num_results,
    }
    # Add optional parameters if provided
    if return_date:
        params["returnDate"] = return_date
    if max_price:
        params["maxPrice"] = max_price

    url = "https://test.api.amadeus.com/v2/shopping/flight-offers"

    # Make API request with comprehensive error handling
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code == 400:
            return {
                "status": "error",
                "error_type": "invalid_parameters",
                "message": "Invalid flight search parameters. Verify that origin/destination codes are valid IATA codes (e.g., 'SYD', 'JFK'), dates are in YYYY-MM-DD format and in the future, and travel class is one of: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST.",
                "details": resp.text
            }
        elif resp.status_code == 401:
            return {
                "status": "error",
                "error_type": "authentication_failed",
                "message": "Authentication failed. The Amadeus API token may be expired or invalid. Please retry the request.",
                "details": resp.text
            }
        elif resp.status_code == 404:
            return {
                "status": "error",
                "error_type": "no_results",
                "message": "No flights found for this route and date combination. Try different dates, nearby airports, or check that the IATA airport codes are correct.",
                "details": resp.text
            }
        elif resp.status_code == 429:
            return {
                "status": "error",
                "error_type": "rate_limit_exceeded",
                "message": "Too many requests to Amadeus API. Please wait a moment before trying again.",
                "details": resp.text
            }
        elif resp.status_code != 200:
            return {
                "status": "error",
                "error_type": "api_error",
                "message": f"Amadeus API returned error {resp.status_code}. Please try again or contact support if the issue persists.",
                "details": resp.text
            }

        # Parse successful response
        response_data = resp.json()
        # Check if any flights were found
        if not response_data.get("data"):
            return {
                "status": "success",
                "count": 0,
                "message": "No flights found for this route and date combination. Try different dates or nearby airports.",
                "flights": []
            }

        # Transform and return simplified flight data
        return simplify_flights_response(response_data)

    except httpx.TimeoutException:
        return {
            "status": "error",
            "error_type": "timeout",
            "message": "Request to Amadeus API timed out. Please try again.",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "unexpected_error",
            "message": f"An unexpected error occurred: {str(e)}. Please try again.",
        }
