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

            # Add a custom suggestion based on the weather
            if "rain" in weather.lower():
                suggestion = f"It's rainy in {city}. Don't forget your umbrella! 🌧️ Maybe enjoy a cozy day indoors with a book."
            elif "clear" in weather.lower():
                suggestion = f"It's a sunny day in {city}! Perfect for a walk or a picnic. ☀️ Don't forget your sunglasses!"
            elif "cloud" in weather.lower():
                suggestion = f"It's cloudy in {city}. A great day to grab a warm drink and explore the city. ☁️"
            elif "snow" in weather.lower():
                suggestion = f"It's snowing in {city}! Stay warm and maybe build a snowman. ❄️"
            else:
                suggestion = f"The weather in {city} is {weather}. Have a great day, no matter the weather! 🌈"

            return {
                "success": True,
                "city": city,
                "country": country,
                "weather": weather,
                "temp": temp,
                "feels_like": feels_like,
                "humidity": humidity,
                "suggestion": suggestion
            }
        else:
            return {"success": False, "error": f"API error: {response.status_code} - {response.text}"}
    except Exception as e:
        return {"success": False, "error": f"Exception occurred: {str(e)}"}
# --- END Weather skill support ---
