# --- BEGIN Weather skill support ---

SKILL_FUNCTION_DECLARATIONS = [
    {
        "name": "get_current_weather",
        "description": "Get the current weather for a location (city required, country optional).",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "country": {"type": "string", "description": "Country two-letter code (optional)"}
            },
            "required": ["city"]
        }
    }
]

import requests

def get_current_weather(city, country=None):
    # Use your actual OpenWeatherMap API key here
    API_KEY = "898ae0941aeea4b30cd77353a9b5b34d"
    location = city if not country else f"{city},{country}"
    url = f"https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": location,
        "appid": API_KEY,
        "units": "metric"
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            weather = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            humidity = data["main"]["humidity"]
            return {
                "success": True,
                "city": city,
                "country": country,
                "weather": weather,
                "temp": temp,
                "feels_like": feels_like,
                "humidity": humidity
            }
        else:
            return {"success": False, "error": f"API error: {response.status_code} - {response.text}"}
    except Exception as e:
        return {"success": False, "error": f"Exception occurred: {str(e)}"}
# --- END Weather skill support ---
