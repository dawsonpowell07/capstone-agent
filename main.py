from agent.nodes.flight_agent import search_flights

resp = search_flights(
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

print(resp)