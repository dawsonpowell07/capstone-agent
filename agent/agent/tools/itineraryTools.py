"""
Itinerary Management Tools - CRUD operations for travel itineraries in Azure Cosmos DB.

This module provides LangGraph tools for managing travel itineraries:
- get_itinerary: Retrieve a specific itinerary by ID
- update_itinerary: Update itinerary-level fields
- add_flight_to_itinerary: Add flights with airport verification
- add_accommodation_to_itinerary: Add hotels with location verification
- add_activity_to_itinerary: Add activities with location verification
- add_restaurant_to_itinerary: Add restaurants with location verification

All location-based additions automatically verify addresses using Azure Maps API
and store detailed geographic data for frontend map display.
"""

from typing import Literal, Optional, TypedDict, Annotated
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from langchain_core.tools import tool
from config import get_settings
from datetime import datetime
import httpx

settings = get_settings()

# Global variables for lazy initialization of async Cosmos DB client
# This avoids creating a new client for each tool call
_cosmos_client = None
_database = None
_container = None

# Get or create the async Cosmos DB container client.


async def get_container():
    global _cosmos_client, _database, _container

    if _container is None:
        _cosmos_client = CosmosClient(
            url=settings.cosmos_db_endpoint,
            credential=settings.cosmos_db_key
        )
        _database = _cosmos_client.get_database_client(
            settings.cosmos_db_database_name)
        _container = _database.get_container_client("itineraries")

    return _container


async def verify_location_with_azure_maps(
    name: str,
    city: str,
    country: Optional[str] = None
) -> Optional[dict]:
    """Verify and geocode a location using Azure Maps Fuzzy Search API.

    This helper function takes a place name and location, searches Azure Maps,
    and returns detailed address information including coordinates. Used by
    all add_* functions to verify locations before storing in the database.

    The function gracefully degrades if:
    - Azure Maps API key is not configured
    - API call fails
    - No results are found

    Args:
        name: Name of the place (hotel, restaurant, activity, etc.)
        city: City where the place is located
        country: Optional country name or code for better accuracy

    Returns:
        dict: Azure Maps data with address and coordinates, or None if verification fails
            {
                "freeformAddress": "123 Main St, Paris, France",
                "municipality": "Paris",
                "countrySubdivision": "Île-de-France",
                "postalCode": "75001",
                "country": "France",
                "countryCode": "FR",
                "latitude": 48.8566,
                "longitude": 2.3522
            }
    """
    # Check if Azure Maps API key is configured
    azure_maps_key = getattr(settings, 'azure_maps_api_key', None)
    if not azure_maps_key:
        # If no key configured, return None (gracefully degrade)
        return None

    # Build search query combining name, city, and country
    query = f"{name}, {city}"
    if country:
        query += f", {country}"

    # Country code mapping for better search results (Azure Maps prefers ISO codes)
    country_code = None
    if country:
        country_mapping = {
            "USA": "US", "United States": "US",
            "UK": "GB", "United Kingdom": "GB",
            "France": "FR", "Germany": "DE", "Spain": "ES",
            "Italy": "IT", "Japan": "JP", "China": "CN",
            "Canada": "CA", "Australia": "AU", "Mexico": "MX",
            "India": "IN", "Brazil": "BR", "Netherlands": "NL"
        }
        country_code = country_mapping.get(
            country, country[:2].upper() if len(country) == 2 else None)

    # Build Azure Maps Fuzzy Search API request
    url = "https://atlas.microsoft.com/search/fuzzy/json"
    params = {
        "api-version": "1.0",
        "subscription-key": azure_maps_key,
        "query": query,
        "limit": 1,  # Only need best match
        "typeahead": False,
    }

    if country_code:
        params["countrySet"] = country_code

    try:
        # Call Azure Maps API with timeout
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)

        if response.status_code != 200:
            # If API call fails, return None (gracefully degrade)
            return None

        # Parse response and extract results
        data = response.json()
        results = data.get("results", [])

        if not results:
            # No matching location found, return None
            return None

        # Extract address and coordinates from the best match
        result = results[0]
        address_info = result.get("address", {})
        position = result.get("position", {})

        # Build standardized Azure Maps data object for storage
        azure_maps_data = {
            "freeformAddress": address_info.get("freeformAddress", ""),
            "municipality": address_info.get("municipality") or address_info.get("municipalitySubdivision", ""),
            "countrySubdivision": address_info.get("countrySubdivision", ""),
            "postalCode": address_info.get("postalCode", ""),
            "country": address_info.get("country", ""),
            "countryCode": address_info.get("countryCode", ""),
            "latitude": position.get("lat"),
            "longitude": position.get("lon")
        }

        return azure_maps_data

    except Exception:
        # If anything fails, return None (gracefully degrade)
        return None


# ============================================================================
# TYPE DEFINITIONS
# TypedDict classes that define the structure of itinerary components
# These match the schema used in Azure Cosmos DB and the frontend
# ============================================================================

class Flight(TypedDict, total=False):
    airline: str
    flightNumber: str
    departure: dict  # {airport: str, time: str, azureMapsData: Optional[dict]}
    arrival: dict    # {airport: str, time: str, azureMapsData: Optional[dict]}
    seat: Optional[str]
    confirmation: Optional[str]
    cost: Optional[float]


class Activity(TypedDict, total=False):
    name: str
    description: Optional[str]
    date: Optional[str]
    time: Optional[str]
    location: Optional[str]
    cost: Optional[float]
    bookingConfirmation: Optional[str]
    azureMapsData: Optional[dict]  # Verified location data from Azure Maps


class Accommodation(TypedDict, total=False):
    name: str
    type: str  # 'hotel', 'airbnb', 'resort', etc.
    checkIn: str
    checkOut: str
    address: Optional[str]
    confirmation: Optional[str]
    cost: Optional[float]
    azureMapsData: Optional[dict]  # Verified location data from Azure Maps


class Restaurant(TypedDict, total=False):
    name: str
    cuisine: Optional[str]
    date: Optional[str]
    time: Optional[str]
    address: Optional[str]
    reservationConfirmation: Optional[str]
    cost: Optional[float]
    azureMapsData: Optional[dict]  # Verified location data from Azure Maps


class Itinerary(TypedDict, total=False):
    id: str
    userId: str
    profileId: Optional[str]
    title: str
    destination: str
    startDate: str
    endDate: str
    status: Literal['planning', 'booked', 'completed', 'cancelled']
    budget: Optional[float]
    currency: Optional[str]
    flights: list[Flight]
    activities: list[Activity]
    accommodations: list[Accommodation]
    restaurants: list[Restaurant]
    notes: Optional[str]
    createdAt: Optional[str]
    updatedAt: Optional[str]


# ============================================================================
# ITINERARY CRUD TOOLS
# LangGraph tools for managing travel itineraries in Azure Cosmos DB
# All tools handle errors gracefully and return structured responses
# ============================================================================

@tool
async def get_itinerary(
    user_id: Annotated[str, "User ID who owns the itinerary"],
    itinerary_id: Annotated[str, "ID of the itinerary to retrieve"],
) -> dict:
    """
    Get a specific itinerary by ID.

    Returns the full itinerary details including all flights, activities, accommodations, and restaurants.
    """
    try:
        container = await get_container()
        # Read the item from Cosmos DB using id and partition key (userId)
        item = await container.read_item(item=itinerary_id, partition_key=user_id)
        return {
            "status": "success",
            "message": f"Successfully retrieved itinerary '{item.get('title', itinerary_id)}'.",
            "itinerary": item
        }
    except CosmosResourceNotFoundError:
        return {
            "status": "error",
            "error_type": "not_found",
            "message": f"Itinerary with ID '{itinerary_id}' not found for user '{user_id}'. Verify that both the itinerary_id and user_id are correct.",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "database_error",
            "message": "Failed to retrieve itinerary from database. This may be a temporary connection issue.",
            "details": str(e)
        }


@tool
async def update_itinerary(
    user_id: Annotated[str, "User ID who owns the itinerary"],
    itinerary_id: Annotated[str, "ID of the itinerary to update"],
    title: Annotated[Optional[str], "New title"] = None,
    destination: Annotated[Optional[str], "New destination"] = None,
    start_date: Annotated[Optional[str], "New start date (YYYY-MM-DD)"] = None,
    end_date: Annotated[Optional[str], "New end date (YYYY-MM-DD)"] = None,
    status: Annotated[
        Optional[Literal['planning', 'booked', 'completed', 'cancelled']],
        "New status"
    ] = None,
    budget: Annotated[Optional[float], "New budget amount"] = None,
    currency: Annotated[Optional[str], "New currency code"] = None,
    flights: Annotated[Optional[list[dict]], "Updated flights list"] = None,
    activities: Annotated[Optional[list[dict]],
                          "Updated activities list"] = None,
    accommodations: Annotated[Optional[list[dict]],
                              "Updated accommodations list"] = None,
    restaurants: Annotated[Optional[list[dict]],
                           "Updated restaurants list"] = None,
    notes: Annotated[Optional[str], "Updated notes"] = None,
    profile_id: Annotated[Optional[str], "Profile ID"] = None,
) -> dict:
    """
    Update an existing itinerary. Only provided fields will be updated.

    Can update basic info (title, dates, status) or add/modify flights, activities,
    accommodations, and restaurants.

    Returns the updated itinerary.
    """
    try:
        container = await get_container()
        # First, get the existing itinerary
        existing = await container.read_item(
            item=itinerary_id, partition_key=user_id)

        # Validate dates if provided
        if start_date or end_date:
            try:
                start = datetime.fromisoformat(
                    start_date if start_date else existing.get("startDate"))
                end = datetime.fromisoformat(
                    end_date if end_date else existing.get("endDate"))

                if start >= end:
                    return {
                        "status": "error",
                        "error_type": "validation_error",
                        "message": "Invalid dates: start date must be before end date. Please provide valid dates.",
                    }
            except ValueError as e:
                return {
                    "status": "error",
                    "error_type": "validation_error",
                    "message": "Invalid date format. Dates must be in YYYY-MM-DD format (e.g., '2025-06-15').",
                    "details": str(e)
                }

        # Build the update payload - only include fields that were provided
        if title is not None:
            existing["title"] = title
        if destination is not None:
            existing["destination"] = destination
        if start_date is not None:
            existing["startDate"] = start_date
        if end_date is not None:
            existing["endDate"] = end_date
        if status is not None:
            existing["status"] = status
        if budget is not None:
            existing["budget"] = budget
        if currency is not None:
            existing["currency"] = currency
        if flights is not None:
            existing["flights"] = flights
        if activities is not None:
            existing["activities"] = activities
        if accommodations is not None:
            existing["accommodations"] = accommodations
        if restaurants is not None:
            existing["restaurants"] = restaurants
        if notes is not None:
            existing["notes"] = notes
        if profile_id is not None:
            existing["profileId"] = profile_id

        # Update timestamp
        existing["updatedAt"] = datetime.utcnow().isoformat()

        # Upsert the item (replace it)
        updated = await container.upsert_item(body=existing)

        return {
            "status": "success",
            "message": f"Successfully updated itinerary '{updated.get('title', itinerary_id)}'. do not call this tool again.",
            "itinerary": updated
        }
    except CosmosResourceNotFoundError:
        return {
            "status": "error",
            "error_type": "not_found",
            "message": f"Itinerary with ID '{itinerary_id}' not found for user '{user_id}'. Verify that both the itinerary_id and user_id are correct.",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "database_error",
            "message": "Failed to update itinerary in database. This may be a temporary connection issue.",
            "details": str(e)
        }


@tool
async def add_flight_to_itinerary(
    user_id: Annotated[str, "User ID who owns the itinerary"],
    itinerary_id: Annotated[str, "ID of the itinerary"],
    airline: Annotated[str, "Airline name"],
    flight_number: Annotated[str, "Flight number"],
    departure_airport: Annotated[str, "Departure airport code (e.g., 'JFK', 'LAX')"],
    departure_time: Annotated[str, "Departure time (ISO format)"],
    arrival_airport: Annotated[str, "Arrival airport code (e.g., 'NRT', 'CDG')"],
    arrival_time: Annotated[str, "Arrival time (ISO format)"],
    seat: Annotated[Optional[str], "Seat number"] = None,
    confirmation: Annotated[Optional[str], "Confirmation number"] = None,
    cost: Annotated[Optional[float], "Flight cost"] = None,
) -> dict:
    """
    Add a flight to an existing itinerary.

    Automatically verifies airport locations using Azure Maps and stores detailed address data.
    """
    # Retrieve the current itinerary to get existing flights list
    get_response = await get_itinerary.ainvoke({"user_id": user_id, "itinerary_id": itinerary_id})
    if get_response.get("status") == "error":
        # If itinerary doesn't exist or error occurs, propagate the error
        return get_response

    itinerary = get_response.get("itinerary", {})
    flights = itinerary.get("flights", [])

    # Verify airport locations with Azure Maps for accurate coordinates
    # This enables the frontend to display flights on a map
    departure_maps_data = await verify_location_with_azure_maps(
        f"{departure_airport} airport",
        "",  # No specific city needed for airport codes
        None
    )
    arrival_maps_data = await verify_location_with_azure_maps(
        f"{arrival_airport} airport",
        "",  # No specific city needed for airport codes
        None
    )

    # Build new flight object with required fields
    new_flight = {
        "airline": airline,
        "flightNumber": flight_number,
        "departure": {
            "airport": departure_airport,
            "time": departure_time
        },
        "arrival": {
            "airport": arrival_airport,
            "time": arrival_time
        },
    }

    # Attach Azure Maps verified location data if available
    if departure_maps_data:
        new_flight["departure"]["azureMapsData"] = departure_maps_data

    if arrival_maps_data:
        new_flight["arrival"]["azureMapsData"] = arrival_maps_data

    # Add optional fields if provided
    if seat:
        new_flight["seat"] = seat
    if confirmation:
        new_flight["confirmation"] = confirmation
    if cost is not None:
        new_flight["cost"] = cost

    # Append new flight to existing flights list
    flights.append(new_flight)

    # Save updated flights list to Cosmos DB
    return await update_itinerary.ainvoke({
        "user_id": user_id,
        "itinerary_id": itinerary_id,
        "flights": flights
    })


@tool
async def add_accommodation_to_itinerary(
    user_id: Annotated[str, "User ID who owns the itinerary"],
    itinerary_id: Annotated[str, "ID of the itinerary"],
    name: Annotated[str, "Accommodation name"],
    accommodation_type: Annotated[str, "Type (hotel, airbnb, resort, etc.)"],
    check_in: Annotated[str, "Check-in date (YYYY-MM-DD)"],
    check_out: Annotated[str, "Check-out date (YYYY-MM-DD)"],
    city: Annotated[str, "City where the accommodation is located"],
    country: Annotated[Optional[str],
                       "Country where the accommodation is located"] = None,
    address: Annotated[Optional[str],
                       "Address (will be verified via Azure Maps)"] = None,
    confirmation: Annotated[Optional[str], "Booking confirmation"] = None,
    cost: Annotated[Optional[float], "Total cost"] = None,
) -> dict:
    """
    Add accommodation to an existing itinerary.

    Automatically verifies the location using Azure Maps and stores detailed address data.
    """
    # Get current itinerary
    get_response = await get_itinerary.ainvoke({"user_id": user_id, "itinerary_id": itinerary_id})
    if get_response.get("status") == "error":
        return get_response

    itinerary = get_response.get("itinerary", {})
    accommodations = itinerary.get("accommodations", [])

    # Verify location with Azure Maps
    azure_maps_data = await verify_location_with_azure_maps(name, city, country)

    # Add new accommodation
    new_accommodation = {
        "name": name,
        "type": accommodation_type,
        "checkIn": check_in,
        "checkOut": check_out,
    }

    # Use Azure Maps verified address if available, otherwise use provided address
    if azure_maps_data:
        new_accommodation["address"] = azure_maps_data.get(
            "freeformAddress", address or "")
        new_accommodation["azureMapsData"] = azure_maps_data
    elif address:
        new_accommodation["address"] = address

    if confirmation:
        new_accommodation["confirmation"] = confirmation
    if cost is not None:
        new_accommodation["cost"] = cost

    accommodations.append(new_accommodation)

    # Update the itinerary
    return await update_itinerary.ainvoke({
        "user_id": user_id,
        "itinerary_id": itinerary_id,
        "accommodations": accommodations
    })


@tool
async def add_activity_to_itinerary(
    user_id: Annotated[str, "User ID who owns the itinerary"],
    itinerary_id: Annotated[str, "ID of the itinerary"],
    name: Annotated[str, "Activity name"],
    city: Annotated[str, "City where the activity is located"],
    country: Annotated[Optional[str],
                       "Country where the activity is located"] = None,
    description: Annotated[Optional[str], "Activity description"] = None,
    date: Annotated[Optional[str], "Activity date (YYYY-MM-DD)"] = None,
    time: Annotated[Optional[str], "Activity time"] = None,
    location: Annotated[Optional[str],
                        "Activity location (will be verified via Azure Maps)"] = None,
    cost: Annotated[Optional[float], "Activity cost"] = None,
    booking_confirmation: Annotated[Optional[str],
                                    "Booking confirmation"] = None,
) -> dict:
    """
    Add an activity to an existing itinerary.

    Automatically verifies the location using Azure Maps and stores detailed address data.
    """
    # Get current itinerary
    get_response = await get_itinerary.ainvoke({"user_id": user_id, "itinerary_id": itinerary_id})
    if get_response.get("status") == "error":
        return get_response

    itinerary = get_response.get("itinerary", {})
    activities = itinerary.get("activities", [])

    # Verify location with Azure Maps
    azure_maps_data = await verify_location_with_azure_maps(name, city, country)

    # Add new activity
    new_activity = {"name": name}
    if description:
        new_activity["description"] = description
    if date:
        new_activity["date"] = date
    if time:
        new_activity["time"] = time

    # Use Azure Maps verified address if available, otherwise use provided location
    if azure_maps_data:
        new_activity["location"] = azure_maps_data.get(
            "freeformAddress", location or "")
        new_activity["azureMapsData"] = azure_maps_data
    elif location:
        new_activity["location"] = location

    if cost is not None:
        new_activity["cost"] = cost
    if booking_confirmation:
        new_activity["bookingConfirmation"] = booking_confirmation

    activities.append(new_activity)

    # Update the itinerary
    return await update_itinerary.ainvoke({
        "user_id": user_id,
        "itinerary_id": itinerary_id,
        "activities": activities
    })


@tool
async def add_restaurant_to_itinerary(
    user_id: Annotated[str, "User ID who owns the itinerary"],
    itinerary_id: Annotated[str, "ID of the itinerary"],
    name: Annotated[str, "Restaurant name"],
    city: Annotated[str, "City where the restaurant is located"],
    country: Annotated[Optional[str],
                       "Country where the restaurant is located"] = None,
    cuisine: Annotated[Optional[str], "Cuisine type"] = None,
    date: Annotated[Optional[str], "Reservation date (YYYY-MM-DD)"] = None,
    time: Annotated[Optional[str], "Reservation time"] = None,
    address: Annotated[Optional[str],
                       "Restaurant address (will be verified via Azure Maps)"] = None,
    reservation_confirmation: Annotated[Optional[str],
                                        "Confirmation number"] = None,
    cost: Annotated[Optional[float], "Estimated cost"] = None,
) -> dict:
    """
    Add a restaurant reservation to an existing itinerary.

    Automatically verifies the location using Azure Maps and stores detailed address data.
    """
    # Get current itinerary
    get_response = await get_itinerary.ainvoke({"user_id": user_id, "itinerary_id": itinerary_id})
    if get_response.get("status") == "error":
        return get_response

    itinerary = get_response.get("itinerary", {})
    restaurants = itinerary.get("restaurants", [])

    # Verify location with Azure Maps
    azure_maps_data = await verify_location_with_azure_maps(name, city, country)

    # Add new restaurant
    new_restaurant = {"name": name}
    if cuisine:
        new_restaurant["cuisine"] = cuisine
    if date:
        new_restaurant["date"] = date
    if time:
        new_restaurant["time"] = time

    # Use Azure Maps verified address if available, otherwise use provided address
    if azure_maps_data:
        new_restaurant["address"] = azure_maps_data.get(
            "freeformAddress", address or "")
        new_restaurant["azureMapsData"] = azure_maps_data
    elif address:
        new_restaurant["address"] = address

    if reservation_confirmation:
        new_restaurant["reservationConfirmation"] = reservation_confirmation
    if cost is not None:
        new_restaurant["cost"] = cost

    restaurants.append(new_restaurant)

    # Update the itinerary
    return await update_itinerary.ainvoke({
        "user_id": user_id,
        "itinerary_id": itinerary_id,
        "restaurants": restaurants
    })


# ============================================================================
# TOOL COLLECTION
# Export all itinerary tools as a list for easy import by the itinerary agent
# ============================================================================

ITINERARY_TOOLS = [
    get_itinerary,
    update_itinerary,
    add_flight_to_itinerary,
    add_accommodation_to_itinerary,
    add_activity_to_itinerary,
    add_restaurant_to_itinerary,
]


# # Test functions
# async def test_itinerary_tools():
#     """Test the itinerary tools with CosmosDB."""

#     # Test user ID (replace with a real user ID from your database)
#     test_user_id = "google-oauth2|109357952475421267138"
#     test_itinerary_id = "2967497d-1fd7-44ef-a162-5bec0acc9006"

#     print("=" * 60)
#     print("TESTING ITINERARY TOOLS")
#     print("=" * 60)

#     # Test 2: Get specific itinerary (if we have one)
#     if test_itinerary_id:
#         print(f"\n2. Testing get_itinerary with ID: {test_itinerary_id}...")
#         try:
#             result = await get_itinerary.ainvoke({
#                 "user_id": test_user_id,
#                 "itinerary_id": test_itinerary_id
#             })
#             print(f"✓ Get itinerary result: {result}")
#         except Exception as e:
#             print(f"✗ Error getting itinerary: {e}")

#     #     # Test 3: Update itinerary status
#     #     print("\n3. Testing update_itinerary...")
#     #     try:
#     #         result = await update_itinerary.ainvoke({
#     #             "user_id": test_user_id,
#     #             "itinerary_id": test_itinerary_id,
#     #             "status": "planning",
#     #             "notes": "Updated via test script"
#     #         })
#     #         print(f"✓ Update itinerary result: {result}")
#     #     except Exception as e:
#     #         print(f"✗ Error updating itinerary: {e}")

#     #     # Test 4: Add a flight
#     #     print("\n4. Testing add_flight_to_itinerary...")
#     #     try:
#     #         result = await add_flight_to_itinerary.ainvoke({
#     #             "user_id": test_user_id,
#     #             "itinerary_id": test_itinerary_id,
#     #             "airline": "Test Airlines",
#     #             "flight_number": "TA123",
#     #             "departure_airport": "JFK",
#     #             "departure_time": "2025-06-01T10:00:00",
#     #             "arrival_airport": "LAX",
#     #             "arrival_time": "2025-06-01T13:00:00",
#     #             "seat": "12A",
#     #             "cost": 350.00
#     #         })
#     #         print(f"✓ Add flight result: {result}")
#     #     except Exception as e:
#     #         print(f"✗ Error adding flight: {e}")

#     #     # Test 5: Add an accommodation
#     #     print("\n5. Testing add_accommodation_to_itinerary...")
#     #     try:
#     #         result = await add_accommodation_to_itinerary.ainvoke({
#     #             "user_id": test_user_id,
#     #             "itinerary_id": test_itinerary_id,
#     #             "name": "Test Hotel",
#     #             "accommodation_type": "hotel",
#     #             "check_in": "2025-06-01",
#     #             "check_out": "2025-06-05",
#     #             "address": "123 Test St",
#     #             "cost": 500.00
#     #         })
#     #         print(f"✓ Add accommodation result: {result}")
#     #     except Exception as e:
#     #         print(f"✗ Error adding accommodation: {e}")

#     #     # Test 6: Add an activity
#     #     print("\n6. Testing add_activity_to_itinerary...")
#     #     try:
#     #         result = await add_activity_to_itinerary.ainvoke({
#     #             "user_id": test_user_id,
#     #             "itinerary_id": test_itinerary_id,
#     #             "name": "Test Activity",
#     #             "description": "A fun test activity",
#     #             "date": "2025-06-02",
#     #             "time": "14:00",
#     #             "location": "Test Location",
#     #             "cost": 50.00
#     #         })
#     #         print(f"✓ Add activity result: {result}")
#     #     except Exception as e:
#     #         print(f"✗ Error adding activity: {e}")

#     #     # Test 7: Add a restaurant
#     #     print("\n7. Testing add_restaurant_to_itinerary...")
#     #     try:
#     #         result = await add_restaurant_to_itinerary.ainvoke({
#     #             "user_id": test_user_id,
#     #             "itinerary_id": test_itinerary_id,
#     #             "name": "Test Restaurant",
#     #             "cuisine": "Italian",
#     #             "date": "2025-06-03",
#     #             "time": "19:00",
#     #             "address": "456 Food Ave",
#     #             "cost": 100.00
#     #         })
#     #         print(f"✓ Add restaurant result: {result}")
#     #     except Exception as e:
#     #         print(f"✗ Error adding restaurant: {e}")
#     # else:
#     #     print("\n⚠ No existing itinerary found. Skipping update/add tests.")
#     #     print("Please create an itinerary first using the frontend or API.")

#     print("\n" + "=" * 60)
#     print("TESTS COMPLETED")
#     print("=" * 60)


# if __name__ == "__main__":
#     """
#     Run tests when executed directly.

#     Usage:
#         python -m agent.tools.itineraryTools

#     Make sure to update test_user_id in test_itinerary_tools()
#     with a real user ID from your database.
#     """
#     import asyncio
#     asyncio.run(test_itinerary_tools())
