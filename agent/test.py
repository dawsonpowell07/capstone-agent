import requests
from config import get_settings

config = get_settings()
API_KEY = config.google_maps_api
PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"


def search_nearby_places(latitude: float, longitude: float, radius: float = 1000, included_types=None, max_results: int = 10):
    """
    Query the Google Places API for nearby places.

    Args:
        latitude (float): Center latitude
        longitude (float): Center longitude
        radius (float): Search radius in meters (max 50,000)
        included_types (list[str]): Place types (e.g., ["restaurant", "hotel"])
        max_results (int): Number of results to return (max 20)

    Returns:
        list[dict]: List of places with name, address, and other data.
    """
    if included_types is None:
        included_types = ["restaurant"]

    # Construct request body
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

    field_mask = "places.displayName,places.formattedAddress,places.types,places.websiteUri,places.rating,places.userRatingCount"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": field_mask
    }

    # Send POST request
    response = requests.post(PLACES_URL, headers=headers, json=payload)

    # Handle response
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return []

    data = response.json()
    places = data.get("places", [])

    # Simplify output
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

    return results
