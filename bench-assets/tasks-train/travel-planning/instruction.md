## Task
Build an itinerary for the user according to the following requirements:
"We need a 5-day travel itinerary for a group of three departing from Denver and visiting three cities in Texas, from April 5th to April 9th, 2022. Our total budget is $4,200. We will be traveling with children, so we need child-friendly accommodations that do not prohibit children. Our dining preferences include Mexican, Indian, French, and Chinese cuisines. We prefer not to fly, so the plan should exclude any flights."

## Rules
- You must utilize skills to search for real-world data in the database, do not use data/POIs from your memory.

## Output Format (JSON file)

Produce a single JSON file to `/app/output/trip_plan.json` with the following structure:

**Top-level keys:**
- `itinerary`: array of exactly 5 day objects (see below)
- `tools_used`: array of strings listing all search skills used (e.g., `["search_cities", "search_accommodations", ...]`)

**Each day object in `itinerary` must contain:**
- `day_number`: integer day number (1–5)
- `location`: string (city name, or `"from A to B"` when moving between cities)
- `transport`: string (e.g., `"Self-driving: from A to B"`; do not use flights)
- `morning_meal`, `midday_meal`, `evening_meal`: string; use `"-"` if intentionally skipped
- `sightseeing`: string; list multiple attractions separated by `;` and end with `;` (e.g., `"Space Center Houston;Hermann Park;"`)
- `lodging`: string; child-friendly lodging

**Example:**
```json
{
  "itinerary": [
    {
      "day_number": 1,
      "location": "Denver",
      "transport": "Self-driving: from Denver to Houston",
      "morning_meal": "Snooze an A.M. Eatery, Denver",
      "midday_meal": "Mexican cuisine at Tamayo, Denver",
      "evening_meal": "French at Bistro Vendome, Denver",
      "sightseeing": "Denver Art Museum;Red Rocks Amphitheatre;",
      "lodging": "Child-friendly Holiday Inn Houston"
    }
  ],
  "tools_used": ["search_cities", "search_accommodations", "search_restaurants"]
}
```
