"""
City Coordinates Tool - Geocoding using OpenStreetMap Nominatim API.

This tool converts city names into geographic coordinates (latitude/longitude)
using the free OpenStreetMap Nominatim geocoding service. This is used by
hotel and activity agents to convert city names into coordinates for
Google Maps Places API searches.
"""

import httpx


async def get_city_coordinates(city_name: str) -> dict:
    """Convert a city name to geographic coordinates using OpenStreetMap Nominatim.

    Args:
        city_name: Name of the city to geocode (e.g., "Paris, France")

    Returns:
        dict: Status and coordinates if found, or error details
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city_name, "format": "json", "limit": 1}
    # Required User-Agent header for OpenStreetMap API
    headers = {"User-Agent": "AI-Agent/1.0"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)

        if response.status_code == 400:
            return {
                "status": "error",
                "error_type": "invalid_parameters",
                "message": "Invalid city name format. Please provide a valid city name.",
            }
        elif response.status_code == 403:
            return {
                "status": "error",
                "error_type": "access_denied",
                "message": "Access denied by OpenStreetMap API.",
            }
        elif response.status_code == 429:
            return {
                "status": "error",
                "error_type": "rate_limit_exceeded",
                "message": "Too many requests to OpenStreetMap API. Please wait a moment before trying again.",
            }
        elif response.status_code != 200:
            return {
                "status": "error",
                "error_type": "api_error",
                "message": f"OpenStreetMap API returned error {response.status_code}. Please try again.",
            }

        # Parse geocoding results
        data = response.json()

        # Check if city was found
        if not data:
            return {
                "status": "error",
                "error_type": "not_found",
                "message": f"City '{city_name}' not found. Try using the full city name with country (e.g., 'Paris, France') or check the spelling.",
            }

        # Extract coordinates from first result
        city = data[0]
        return {
            "status": "success",
            "message": f"Successfully found coordinates for {city_name}.",
            "city": city_name,
            "latitude": float(city["lat"]),
            "longitude": float(city["lon"])
        }

    except httpx.TimeoutException:
        return {
            "status": "error",
            "error_type": "timeout",
            "message": "Request to OpenStreetMap API timed out. Please try again.",
        }
    except (KeyError, ValueError):
        return {
            "status": "error",
            "error_type": "parsing_error",
            "message": "Failed to parse coordinates from API response. Please try a different city name format.",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "unexpected_error",
            "message": f"An unexpected error occurred: {str(e)}. Please try again.",
        }
