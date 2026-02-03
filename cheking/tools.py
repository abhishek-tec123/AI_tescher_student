# tools.py
from typing import Annotated
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from geopy.geocoders import Nominatim
import requests

# ----------------------------
# Google-like search grounding
# ----------------------------
google_search_tool = TavilySearch(
    max_results=3,
    tavily_api_key = "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")

# ----------------------------
# Nearby places search (OSM)
# ----------------------------
@tool(description="Find nearby places using OpenStreetMap")
def find_nearby_places(
    query: Annotated[str, "What to search for"],
    location: Annotated[str, "City or area name"],
    radius: Annotated[int, "Search radius in meters"] = 3000,
    limit: Annotated[int, "Max results"] = 5,
) -> str:
    try:
        geolocator = Nominatim(user_agent="langgraph_places")
        loc = geolocator.geocode(location)
        if not loc:
            return f"Could not find location '{location}'."

        lat, lon = loc.latitude, loc.longitude

        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["name"~"{query}", i](around:{radius},{lat},{lon});
          node["amenity"~"{query}", i](around:{radius},{lat},{lon});
          node["shop"~"{query}", i](around:{radius},{lat},{lon});
        );
        out body {limit};
        """

        response = requests.get(
            "https://overpass-api.de/api/interpreter",
            params={"data": overpass_query},
        )
        data = response.json().get("elements", [])

        if not data:
            return f"No results found for '{query}' near {location}."

        results = []
        for el in data[:limit]:
            tags = el.get("tags", {})
            name = tags.get("name", "Unnamed place")
            address = ", ".join(
                filter(None, [tags.get("addr:street"), tags.get("addr:city")])
            )
            results.append(f"- {name} | {address or 'Address not available'}")

        return "\n".join(results)

    except Exception as e:
        return f"Error: {str(e)}"
