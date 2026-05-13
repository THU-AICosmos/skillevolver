"""Custom tests for the travel planning task (Texas variant, 5-day trip)."""

import json
import os

PLAN_PATH = "/app/output/trip_plan.json"


def _extract_cities(location: str):
    """Heuristic splitter to collect city mentions from a location string."""
    parts = []
    if not location:
        return parts
    lowered = location.replace(" to ", "|").replace(" from ", "|")
    for piece in lowered.split("|"):
        cleaned = piece.strip().strip(",")
        if cleaned:
            parts.append(cleaned)
    return parts


def test_output_file_exists():
    """Output file should be produced at the expected path."""
    assert os.path.exists(PLAN_PATH), f"Plan JSON not found at {PLAN_PATH}"


def test_itinerary_structure_and_length():
    """Itinerary should be a JSON object with a 5-day itinerary array."""
    with open(PLAN_PATH) as f:
        payload = json.load(f)

    assert isinstance(payload, dict), "Top-level JSON should be an object"
    assert "itinerary" in payload, "Top-level 'itinerary' key missing"
    itin = payload["itinerary"]
    assert isinstance(itin, list), "'itinerary' should be a list"
    assert len(itin) == 5, f"Expected 5 days in itinerary, got {len(itin)}"


def test_required_fields_and_day_numbers():
    """Each day should have required fields and sequential day numbers."""
    with open(PLAN_PATH) as f:
        itin = json.load(f)["itinerary"]

    required = {"day_number", "location", "transport", "morning_meal", "midday_meal", "evening_meal", "sightseeing", "lodging"}
    for idx, day in enumerate(itin, start=1):
        assert isinstance(day, dict), f"Day {idx} entry must be an object"
        missing = required - set(day.keys())
        assert not missing, f"Day {idx} missing fields: {missing}"
        assert day["day_number"] == idx, f"Day numbering should be sequential starting at 1; got {day['day_number']} at position {idx}"


def test_no_flights_in_transport():
    """Transport should respect no-flight preference."""
    with open(PLAN_PATH) as f:
        itin = json.load(f)["itinerary"]

    for idx, day in enumerate(itin, start=1):
        transport = day.get("transport", "") or ""
        assert "flight" not in transport.lower(), f"Day {idx} transport should not include flights"


def test_starts_in_denver():
    """Day 1 should start from Denver."""
    with open(PLAN_PATH) as f:
        itin = json.load(f)["itinerary"]

    day1_loc = str(itin[0].get("location", "")).lower()
    assert "denver" in day1_loc, "Day 1 should start from Denver"


def test_visits_at_least_three_cities():
    """Itinerary should cover at least three distinct cities."""
    with open(PLAN_PATH) as f:
        itin = json.load(f)["itinerary"]

    cities = []
    for day in itin:
        cities.extend(_extract_cities(str(day.get("location", ""))))
    unique_cities = {c.lower() for c in cities if c}
    assert len(unique_cities) >= 3, f"Expected at least 3 distinct cities, got {len(unique_cities)}"


def test_visits_texas_cities():
    """Itinerary should visit cities in Texas (the required destination state)."""
    with open(PLAN_PATH) as f:
        itin = json.load(f)["itinerary"]

    texas_cities = {
        "abilene",
        "amarillo",
        "harlingen",
        "lubbock",
        "college station",
        "corpus christi",
        "wichita falls",
        "waco",
        "san angelo",
        "houston",
        "san antonio",
        "del rio",
        "mission",
        "beaumont",
        "longview",
        "midland",
        "el paso",
        "brownsville",
        "austin",
        "dallas",
        "killeen",
        "laredo",
        "texarkana",
    }

    cities = []
    for day in itin:
        cities.extend(_extract_cities(str(day.get("location", ""))))
    unique_cities = {c.lower() for c in cities if c}

    texas_matches = unique_cities & texas_cities
    assert texas_matches, f"Expected to visit Texas cities, but found: {unique_cities}"


def test_child_friendly_lodging_hint():
    """Lodging strings should signal child-friendly preference."""
    with open(PLAN_PATH) as f:
        itin = json.load(f)["itinerary"]

    child_keywords = ["child", "kid", "family", "children"]
    hints = []
    for day in itin:
        lodging = str(day.get("lodging", "")).lower()
        if any(kw in lodging for kw in child_keywords):
            hints.append(day.get("lodging", ""))
    assert hints, "At least one lodging should indicate child-friendly options (e.g., 'child-friendly', 'family-friendly')"


def test_meals_include_requested_cuisines():
    """Meals should reflect at least 3 of the 4 preferred cuisines by cross-referencing restaurant data."""
    import csv
    from pathlib import Path

    with open(PLAN_PATH) as f:
        itin = json.load(f)["itinerary"]

    # Load restaurant data
    restaurant_path = Path("/app/data/restaurants/clean_restaurant_2022.csv")
    restaurant_cuisines = {}
    if restaurant_path.exists():
        with open(restaurant_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "").strip().lower()
                city = row.get("City", "").strip().lower()
                cuisines = row.get("Cuisines", "").strip().lower()
                if name:
                    restaurant_cuisines[(name, city)] = cuisines
                    if name not in restaurant_cuisines:
                        restaurant_cuisines[name] = cuisines

    # Collect all meals from the plan
    meals = []
    for day in itin:
        for meal_type in ["morning_meal", "midday_meal", "evening_meal"]:
            meal = str(day.get(meal_type, "")).strip()
            if meal and meal != "-":
                meals.append(meal)

    # Check which cuisines are covered
    target_cuisines = {"mexican", "indian", "french", "chinese"}
    covered = set()

    for meal in meals:
        meal_lower = meal.lower()
        if ", " in meal:
            parts = meal.rsplit(", ", 1)
            name = parts[0].strip().lower()
            city = parts[1].strip().lower() if len(parts) > 1 else ""
            cuisines_str = restaurant_cuisines.get((name, city), "")
            if not cuisines_str:
                cuisines_str = restaurant_cuisines.get(name, "")
        else:
            cuisines_str = restaurant_cuisines.get(meal_lower, "")

        cuisines_str = cuisines_str + " " + meal_lower

        for cuisine in target_cuisines:
            if cuisine in cuisines_str:
                covered.add(cuisine)

    assert (
        len(covered) >= 3
    ), f"Expected at least 3 of the 4 preferred cuisines (Mexican, Indian, French, Chinese); found {covered or 'none'}"


def test_sightseeing_non_empty():
    """Sightseeing should not be empty placeholders."""
    with open(PLAN_PATH) as f:
        itin = json.load(f)["itinerary"]

    for idx, day in enumerate(itin, start=1):
        sightseeing = str(day.get("sightseeing", "")).strip()
        assert sightseeing and sightseeing != "-", f"Day {idx} sightseeing should not be empty or '-'"


def test_tools_used_present():
    """tools_used should include all core tools except search-flights (optional)."""
    with open(PLAN_PATH) as f:
        payload = json.load(f)

    assert "tools_used" in payload, "Top-level 'tools_used' key missing"
    tools = payload["tools_used"]
    assert isinstance(tools, list), "'tools_used' should be a list"

    normalized = {str(t).strip().lower() for t in tools}
    required = {
        "search_cities",
        "search_accommodations",
        "search_restaurants",
        "search_attractions",
        "search_driving_distance",
    }

    missing = [t for t in required if t not in normalized]
    assert not missing, f"'tools_used' missing required tools (excluding flights): {missing}"
