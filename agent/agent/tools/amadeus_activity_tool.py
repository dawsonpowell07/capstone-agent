"""
Amadeus Activity Search Tool - Search for tourist activities and attractions.

This tool uses the Amadeus Travel API to find activities, tours, and experiences
near a given location. It handles authentication, error responses, and returns
a simplified format suitable for agent consumption.
"""

import httpx
from langchain_core.tools import tool
from agent.auth.amadeus_auth import AmadeusAuth

# Initialize Amadeus authentication handler
auth = AmadeusAuth()


@tool
async def search_activities_with_amadeus(
    latitude: float,
    longitude: float,
    radius: int = 1,
    max_results: int = 10,
) -> dict:
    """
    Search for nearby tourist activities, attractions, and experiences using the Amadeus API.

    Args:
        latitude (float): Latitude coordinate of the target location (e.g., 41.397158).
        longitude (float): Longitude coordinate of the target location (e.g., 2.160873).
        radius (int): Search radius in kilometers. Default is 1 km (Amadeus supports 0–20 km).
        max_results (int): Maximum number of activities to return.

    Description:
        This tool queries the Amadeus Travel APIs to find popular activities and experiences 
        (such as sightseeing tours, museum visits, excursions, food tastings, etc.) near a 
        specified latitude and longitude. The agent can use it for recommending things to do
        during a trip, building itineraries, or suggesting local attractions.

    Example:
        search_activities_with_amadeus(
            latitude=41.397158,
            longitude=2.160873,
            radius=2,
            max_results=5
        )

    Returns:
        dict: Simplified list of activities with details such as:
            {
                "status": "success",
                "count": 5,
                "activities": [
                    {
                        "id": "12345",
                        "name": "Barcelona Tapas Walking Tour",
                        "rating": 4.7,
                        "price": {"amount": "65.00", "currency": "EUR"},
                        "category": "Food & Drink",
                        "geoCode": {"latitude": 41.3851, "longitude": 2.1734},
                        "bookingLink": "https://...",
                    },
                    ...
                ]
            }
    """
    # Get OAuth2 token for Amadeus API authentication
    token = await auth.get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/vnd.amadeus+json",
    }

    # Build query parameters for the activity search
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "radius": radius,
    }

    url = "https://test.api.amadeus.com/v1/shopping/activities"

    # Make API request
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)

        if response.status_code == 400:
            return {
                "status": "error",
                "error_type": "invalid_parameters",
                "message": "Invalid search parameters. Check that latitude is between -90 and 90, longitude is between -180 and 180, and radius is between 0 and 20 km.",
                "details": response.text
            }
        elif response.status_code == 401:
            return {
                "status": "error",
                "error_type": "authentication_failed",
                "message": "Authentication failed. The Amadeus API token may be expired or invalid.",
                "details": response.text
            }
        elif response.status_code == 404:
            return {
                "status": "error",
                "error_type": "no_results",
                "message": "No activities found at this location. Try increasing the radius or searching a different location.",
                "details": response.text
            }
        elif response.status_code == 429:
            return {
                "status": "error",
                "error_type": "rate_limit_exceeded",
                "message": "Too many requests to Amadeus API. Please wait a moment before trying again.",
                "details": response.text
            }
        elif response.status_code != 200:
            return {
                "status": "error",
                "error_type": "api_error",
                "message": f"Amadeus API returned error {response.status_code}. Please try again or contact support if the issue persists.",
                "details": response.text
            }

        # Extract activity data from successful response
        data = response.json().get("data", [])
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

    if not data:
        return {
            "status": "success",
            "count": 0,
            "message": "No activities found at this location. Try increasing the search radius or selecting a different area.",
            "activities": []
        }

    # Format activities into a simplified structure
    activities = []
    for item in data[:max_results]:
        activities.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "rating": item.get("rating"),
                "price": item.get("price"),
                "category": item.get("category"),
                "geoCode": item.get("geoCode"),
                "bookingLink": item.get("bookingLink"),
            }
        )

    return {
        "status": "success",
        "count": len(activities),
        "message": f"Successfully found {len(activities)} activities. Do not call this tool again.",
        "activities": activities,
    }
