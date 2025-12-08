"""
Google Maps Places API Tools - Search for hotels and activities.

This module provides tools to search for nearby places using the Google Maps
Places API (New). It includes two main search functions:
- search_hotels: Find lodging and accommodations
- search_activities: Find attractions, restaurants, and entertainment

Both tools use the searchNearby endpoint with different place type filters.
"""

import httpx
from config import get_settings
from langchain_core.tools import tool

# Load configuration and API key
config = get_settings()
API_KEY = config.google_maps_api
PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"


async def search_for_places(latitude: float, longitude: float, radius: float = 1000, included_types=None, max_results: int = 10):
    """Core function for searching nearby places using Google Maps Places API.

    Handles API authentication, parameter validation, error responses, and
    formats results into a simplified structure.

    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        radius: Search radius in meters (1-50000)
        included_types: List of Google Maps place types to search for
        max_results: Maximum number of results to return (1-20)

    Returns:
        dict: Status and list of places with details
    """
    if included_types is None:
        included_types = ["restaurant"]

    # Validate and clamp parameters to API limits
    max_results = max(1, min(20, max_results))
    radius = max(1, min(50000, radius))

    payload = {
        "includedTypes": included_types,
        "maxResultCount": max_results,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": radius
            }
        }
    }

    # Specify which fields to return (reduces response size and cost)
    field_mask = (
        "places.displayName,"
        "places.formattedAddress,"
        "places.types,"
        "places.websiteUri,"
        "places.rating,"
        "places.userRatingCount"
    )

    # Build request headers with API key and field mask
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": field_mask
    }

    # Make API request with comprehensive error handling
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(PLACES_URL, headers=headers, json=payload)

        if response.status_code == 400:
            return {
                "status": "error",
                "error_type": "invalid_parameters",
                "message": "Invalid search parameters. Check that latitude is between -90 and 90, longitude is between -180 and 180, radius is between 1 and 50000 meters, and max_results is between 1 and 20.",
                "details": response.text
            }
        elif response.status_code == 401:
            return {
                "status": "error",
                "error_type": "authentication_failed",
                "message": "Google Maps API authentication failed.",
                "details": response.text
            }
        elif response.status_code == 403:
            return {
                "status": "error",
                "error_type": "access_denied",
                "message": "Access denied to Google Maps API. The API key may be invalid, restricted, or the Places API may not be enabled for this project.",
                "details": response.text
            }
        elif response.status_code == 429:
            return {
                "status": "error",
                "error_type": "rate_limit_exceeded",
                "message": "Too many requests to Google Maps API. Please wait a moment before trying again.",
                "details": response.text
            }
        elif response.status_code != 200:
            return {
                "status": "error",
                "error_type": "api_error",
                "message": f"Google Maps API returned error {response.status_code}.",
                "details": response.text
            }

        # Parse successful response
        data = response.json()
        places = data.get("places", [])
    except httpx.TimeoutException:
        return {
            "status": "error",
            "error_type": "timeout",
            "message": "Request to Google Maps API timed out. Please try again.",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "unexpected_error",
            "message": f"An unexpected error occurred: {str(e)}. Please try again.",
        }

    if not places:
        return {
            "status": "success",
            "count": 0,
            "message": "No places found at this location. Try increasing the search radius or searching a different location.",
            "places": []
        }

    # Format places into simplified structure
    results = []
    for p in places:
        results.append({
            "name": p.get("displayName", {}).get("text", "Unknown"),
            "address": p.get("formattedAddress", "N/A"),
            "types": p.get("types", []),
            "website": p.get("websiteUri", None),
            "rating": p.get("rating", None),
            "reviews": p.get("userRatingCount", 0)
        })

    return {
        "status": "success",
        "count": len(results),
        "message": f"Successfully found {len(results)} places. do not call this tool again.",
        "places": results
    }


@tool
async def search_hotels(
    latitude: float,
    longitude: float,
    radius: float = 3000,
    max_results: int = 10,
):
    """
    Search for nearby hotels, lodgings, and accommodations using the Google Places API.

    Args:
        latitude (float): Latitude coordinate of the target location.
        longitude (float): Longitude coordinate of the target location.
        radius (float): Search radius in meters. Default is 3000 (3 km) MUST be with 1 and 50000 inclusive.
        max_results (int): Maximum number of activity results to return MUST be within 1 and 20 inclusive.

    Description:
        This tool allows the search to find nearby hotels, resorts, inns, hostels, and other lodging types
        around a given location. 

    Example:
        search_hotels(
            latitude=40.748817,
            longitude=-73.985428,
            radius=5000,
            max_results=5
        )

    Returns:
        dict: A dictionary containing hotel or lodging search results, each including
              name, type, location, rating, and place ID (depending on API integration).
    """
    # Google Maps place types for lodging and accommodations
    hotel_types = [
        "lodging", "hotel", "resort_hotel", "bed_and_breakfast", "motel",
        "guest_house", "hostel", "campground", "rv_park", "inn"
    ]

    return await search_for_places(latitude, longitude, radius, hotel_types, max_results)


@tool
async def search_activities(
    latitude: float,
    longitude: float,
    radius: float = 3000,
    max_results: int = 10,
):
    """
    Search for fun activities, attractions, and food spots near a location using the Google Places API.

    Args:
        latitude (float): Latitude coordinate of the target location.
        longitude (float): Longitude coordinate of the target location.
        radius (float): Search radius in meters. Default is 3000 (3 km) MUST be with 1 and 50000 inclusive.
        max_results (int): Maximum number of activity results to return MUST be within 1 and 20 inclusive.

    Description:
        This tool can find activites including tourist attractions, restaurants, museums, beaches, hiking areas, and entertainment venues.

    Example:
        search_activities(
            latitude=34.052235,
            longitude=-118.243683,
            radius=4000,
            max_results=8
        )

    Returns:
        dict: A dictionary of activities and attractions near the given coordinates,
              including name, type, location, and rating when available.
    """
    # Google Maps place types for activities, attractions, dining, and entertainment
    activity_types = [
        # Food & Drink
        "restaurant", "cafe", "bar", "coffee_shop", "bakery",
        "fast_food_restaurant", "ice_cream_shop", "pub",
        # Entertainment & Attractions
        "tourist_attraction", "museum", "art_gallery", "zoo",
        "amusement_park", "night_club", "movie_theater",
        "shopping_mall", "bowling_alley", "park", "beach", "aquarium",
        "hiking_area"
    ]

    return await search_for_places(latitude, longitude, radius, activity_types, max_results)
