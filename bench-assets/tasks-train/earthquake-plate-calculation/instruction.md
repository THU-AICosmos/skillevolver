You are a geospatial scientist specializing in volcanic hazard analysis and tectonic plate mapping. I need to identify the volcanic eruption event that occurred furthest from the Australian plate boundary, but still within the Australian plate itself. Use GeoPandas projections for distance calculations. Write the result to `/root/result.json` as a JSON file with the following fields:

- `event_id`: The volcanic event ID
- `location`: The eruption location description
- `timestamp`: The event time in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
- `vei`: The eruption magnitude (VEI equivalent)
- `lat`: The event latitude
- `lon`: The event longitude
- `boundary_distance_km`: Distance to the nearest Australian plate boundary in kilometers (rounded to 2 decimal places)

The volcanic eruption data is provided in `/root/volcanic_eruptions_2023.json`. The tectonic plate boundary data is given in `/root/PB2002_boundaries.json` and `/root/PB2002_plates.json`.
