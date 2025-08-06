from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import os
from dotenv import load_dotenv
import uuid
from pathlib import Path

# Load environment variables
load_dotenv()

app = FastAPI()

# Create uploads directory if it doesn't exist
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)

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

@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    """Upload and save audio file temporarily"""
    try:
        print(f"=== UPLOAD DEBUG START ===")
        print(f"Received file: {file.filename}")
        print(f"Content type: {file.content_type}")
        print(f"File size: {file.size if hasattr(file, 'size') else 'Unknown'}")
        
        # Read file content first to get actual size
        content = await file.read()
        file_size = len(content)
        print(f"Actual file size: {file_size} bytes")
        
        # Validate file size
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file received")
        
        # Validate file type - be more lenient for browser recordings
        if not file.content_type:
            print("No content type provided, assuming audio/webm for browser recording")
            # For browser recordings without content type, assume it's audio
        elif not (file.content_type.startswith('audio/') or 
                 file.content_type == 'application/octet-stream' or
                 'webm' in file.content_type):
            raise HTTPException(status_code=400, detail=f"File must be an audio file. Received: {file.content_type}")
        
        # Generate unique filename
        file_extension = ".webm"  # Default for browser recordings
        if file.filename:
            original_extension = Path(file.filename).suffix
            if original_extension:
                file_extension = original_extension
        
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = uploads_dir / unique_filename
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(content)
        
        print(f"Audio file uploaded successfully: {unique_filename}, Size: {file_size} bytes")
        print(f"=== UPLOAD DEBUG END ===")
        
        return {
            "success": True,
            "filename": unique_filename,
            "original_filename": file.filename or "recording.webm",
            "content_type": file.content_type,
            "size": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "message": "Audio file uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"Upload failed: {str(e)}"
        print(f"Upload exception: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Failed to upload audio file: {error_detail}")

@app.post("/test-upload")
async def test_upload(file: UploadFile = File(...)):
    """Simple test upload endpoint for debugging"""
    try:
        print(f"TEST UPLOAD - File received: {file.filename}")
        print(f"TEST UPLOAD - Content type: {file.content_type}")
        content = await file.read()
        print(f"TEST UPLOAD - File size: {len(content)} bytes")
        return {"status": "success", "filename": file.filename, "size": len(content)}
    except Exception as e:
        print(f"TEST UPLOAD - Error: {str(e)}")
        return {"status": "error", "message": str(e)}
