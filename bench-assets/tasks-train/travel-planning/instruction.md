## Task
Build an itinerary for the user according to the following requirements:
"We need a 5-day travel itinerary for three people departing from Denver and visiting three cities in Texas, from June 10th to June 14th, 2022. Our budget is up to $4,200. We require non-smoking accommodations with room for at least 3 guests. Our preferred cuisines are Mexican, Indian, French, and Chinese. Please note we prefer not to take any flights so our travel plan should not include them."

## Rules
- You must utilize skills to search for real-world data in the database, do not use data/POIs from your memory.

## Output Format (JSON file)

Produce a single JSON file to `/app/output/itinerary.json` with the following structure:

**Top-level keys:**
- `plan`: array of exactly 5 day objects (see below)
- `tool_called`: array of strings listing all search skills used (e.g., `["search_cities", "search_accommodations", ...]`)

**Each day object in `plan` must contain:**
- `day`: integer day number (1–5)
- `current_city`: string (city name, or `"from A to B"` when moving between cities)
- `transportation`: string (e.g., `"Self-driving: from A to B"`; do not use flights)
- `breakfast`, `lunch`, `dinner`: string; use `"-"` if intentionally skipped
- `attraction`: string; list multiple attractions separated by `;` and end with `;` (e.g., `"Space Center Houston;Buffalo Bayou Park;"`)
- `accommodation`: string; non-smoking lodging for at least 3 guests

**Example:**
```json
{
  "plan": [
    {
      "day": 1,
      "current_city": "Denver",
      "transportation": "Self-driving: from Denver to Houston",
      "breakfast": "The Egg & I, Denver",
      "lunch": "Mexican at Tamayo, Denver",
      "dinner": "Chinese at Rangoli, Houston",
      "attraction": "Space Center Houston;Buffalo Bayou Park;",
      "accommodation": "Non-smoking Private Suite, Houston"
    }
  ],
  "tool_called": ["search_cities", "search_accommodations", "search_restaurants"]
}
```
