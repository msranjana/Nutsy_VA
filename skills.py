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

import os
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add Tavily skill to the skill declarations
SKILL_FUNCTION_DECLARATIONS.append({
    "name": "get_real_time_answer",
    "description": "Fetch real-time answers from the Tavily API for a given query.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The user's query to fetch real-time answers."}
        },
        "required": ["query"]
    }
})

def get_current_weather(city, country=None):
    # Load the API key from the environment
    WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
    if not WEATHER_API_KEY:
        return {"success": False, "error": "Weather API key is missing. Please set WEATHER_API_KEY in the environment."}

    location = city if not country else f"{city},{country}"
    url = f"https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": location,
        "appid": WEATHER_API_KEY,
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

def get_real_time_answer(query):
    """Fetch real-time answers from the Tavily API."""
    TAVILY_API_KEY = os.getenv("TAVILY_KEY")
    if not TAVILY_API_KEY:
        return {
            "success": False,
            "error": "Tavily API key is missing. Please set TAVILY_KEY in the environment."
        }

    url = "https://api.tavily.com/search"
    headers = {
        "Authorization": f"Bearer {TAVILY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"query": query}

    logger.info(f"Sending POST request to Tavily API: {url}")
    logger.info(f"Payload: {payload}")

    try:
        response = requests.post(url, headers=headers, json=payload)
        logger.info(f"Response: {response.status_code} - {response.text}")

        if response.status_code == 200:
            data = response.json()

            # Try to get the main answer
            answer = data.get("answer")
            source = "Unknown source"

            # If no direct answer, try to extract from results
            if not answer and data.get("results"):
                top_result = data["results"][0]
                answer = top_result.get("content", "No answer available.")
                source = top_result.get("url", "Unknown source")

            return {
                "success": True,
                "answer": answer or "No answer available.",
                "source": source
            }

        else:
            return {
                "success": False,
                "error": f"API error: {response.status_code} - {response.text}"
            }

    except Exception as e:
        return {"success": False, "error": f"Exception occurred: {str(e)}"}
