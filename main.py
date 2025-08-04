from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

MURF_API_KEY = os.getenv("MURF_API_KEY", "YOUR_MURF_API_KEY")
MURF_API_URL = "https://api.murf.ai/v1/speech/generate"  # Correct Murf API endpoint

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/debug")
async def debug_info():
    return {
        "murf_api_key_set": bool(MURF_API_KEY and MURF_API_KEY != "YOUR_MURF_API_KEY"),
        "murf_api_url": MURF_API_URL,
        "api_key_length": len(MURF_API_KEY) if MURF_API_KEY else 0
    }

@app.get("/voices")
async def get_voices():
    """Get available Murf voices"""
    try:
        headers = {
            "api-key": MURF_API_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.get("https://api.murf.ai/v1/speech/voices", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=500, detail=f"Failed to fetch voices: {response.text}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching voices: {str(e)}")

@app.post("/tts")
async def text_to_speech(payload: dict):
    text = payload.get("text")
    voice_id = payload.get("voice_id", "en-US-julia")  # Default voice
    
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")
    
    headers = {
        "api-key": MURF_API_KEY,  # Murf uses 'api-key' header, not 'Authorization'
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "voiceId": voice_id,
        "format": "MP3",
        "channelType": "MONO",
        "sampleRate": 44100
    }
    
    try:
        print(f"Making request to Murf API: {MURF_API_URL}")
        print(f"Headers: {headers}")
        print(f"Data: {data}")
        
        response = requests.post(MURF_API_URL, json=data, headers=headers)
        
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.text}")
        
        if response.status_code != 200:
            error_detail = f"Murf API returned status {response.status_code}: {response.text}"
            print(f"Error: {error_detail}")
            raise HTTPException(status_code=500, detail=f"Failed to generate audio: {error_detail}")
        
        result = response.json()
        audio_url = result.get("audioFile")  # Murf returns 'audioFile', not 'audio_url'
        
        if not audio_url:
            print(f"No audioFile in response: {result}")
            raise HTTPException(status_code=500, detail="No audio URL returned from Murf API")
            
        return {
            "audio_url": audio_url,
            "audio_length": result.get("audioLengthInSeconds"),
            "consumed_characters": result.get("consumedCharacterCount"),
            "remaining_characters": result.get("remainingCharacterCount")
        }
        
    except requests.exceptions.RequestException as e:
        error_detail = f"Request failed: {str(e)}"
        print(f"Request exception: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to Murf API: {error_detail}")
    except Exception as e:
        error_detail = f"Unexpected error: {str(e)}"
        print(f"Unexpected exception: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {error_detail}")
