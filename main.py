# Day 1: Project Setup
# - Initialize FastAPI backend
# - Serve index.html and static files for frontend (HTML/JS)
# - Basic server setup
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import os
from dotenv import load_dotenv
import uuid
from pathlib import Path
import assemblyai as aai
from google import genai
from pydantic import BaseModel
# Global, in-memory chat history (prototype only)
from typing import Dict, List
chat_history_store: Dict[str, List[Dict[str, str]]] = {}


# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Day 5: Send Audio to the Server
# - Create uploads directory if it doesn't exist
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Day 2: Your First REST TTS Call
# - Murf API key and endpoint setup
MURF_API_KEY = os.getenv("MURF_API_KEY", "YOUR_MURF_API_KEY")
MURF_API_URL = "https://api.murf.ai/v1/speech/generate"  # Correct Murf API endpoint

# Day 6: Implement Server-Side Transcription
# - AssemblyAI configuration
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "YOUR_ASSEMBLYAI_API_KEY")
aai.settings.api_key = ASSEMBLYAI_API_KEY

# Debug print to verify API key is loaded
print(f"AssemblyAI API Key loaded: {'Yes' if ASSEMBLYAI_API_KEY and ASSEMBLYAI_API_KEY != 'YOUR_ASSEMBLYAI_API_KEY' else 'No'}")
print(f"API Key length: {len(ASSEMBLYAI_API_KEY) if ASSEMBLYAI_API_KEY else 0}")
print(f"API Key first 10 chars: {ASSEMBLYAI_API_KEY[:10] if ASSEMBLYAI_API_KEY else 'None'}")

# Day 1: Serve index.html
@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# (Optional) Debug endpoint
@app.get("/debug")
async def debug_info():
    return {
        "murf_api_key_set": bool(MURF_API_KEY and MURF_API_KEY != "YOUR_MURF_API_KEY"),
        "murf_api_url": MURF_API_URL,
        "murf_api_key_length": len(MURF_API_KEY) if MURF_API_KEY else 0,
        "assemblyai_api_key_set": bool(ASSEMBLYAI_API_KEY and ASSEMBLYAI_API_KEY != "YOUR_ASSEMBLYAI_API_KEY"),
        "assemblyai_api_key_length": len(ASSEMBLYAI_API_KEY) if ASSEMBLYAI_API_KEY else 0,
        "assemblyai_api_key_preview": ASSEMBLYAI_API_KEY[:10] + "..." if ASSEMBLYAI_API_KEY and len(ASSEMBLYAI_API_KEY) > 10 else "Not set"
    }

# (Optional) Get available voices
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

# Day 2: TTS endpoint for Murf API
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

# Day 5: Upload audio endpoint
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

# (Optional) Test upload endpoint
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

# Day 6: Transcribe audio file endpoint (AssemblyAI)
@app.post("/transcribe/file")
async def transcribe_audio_file(file: UploadFile = File(...)):
    """Transcribe audio file using AssemblyAI"""
    try:
        print(f"=== TRANSCRIPTION DEBUG START ===")
        print(f"Received file for transcription: {file.filename}")
        print(f"Content type: {file.content_type}")
        # Read the audio file content
        audio_data = await file.read()
        file_size = len(audio_data)
        print(f"Audio file size: {file_size} bytes")
        # Validate file size
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty audio file received")
        # Validate API key
        if not ASSEMBLYAI_API_KEY or ASSEMBLYAI_API_KEY == "YOUR_ASSEMBLYAI_API_KEY":
            raise HTTPException(status_code=500, detail="AssemblyAI API key not configured")
        # Create transcriber instance
        transcriber = aai.Transcriber()
        print("Starting transcription with AssemblyAI...")
        # Transcribe the audio data directly (no need to save file)
        transcript = transcriber.transcribe(audio_data)
        print(f"Transcription status: {transcript.status}")
        # Check if transcription was successful
        if transcript.status == aai.TranscriptStatus.error:
            error_detail = f"Transcription failed: {transcript.error}"
            print(f"AssemblyAI error: {error_detail}")
            raise HTTPException(status_code=500, detail=error_detail)
        print(f"Transcription completed successfully")
        print(f"Transcript text (first 100 chars): {transcript.text[:100]}...")
        print(f"=== TRANSCRIPTION DEBUG END ===")
        return {
            "success": True,
            "transcript": transcript.text,
            "confidence": getattr(transcript, 'confidence', None),
            "audio_duration": getattr(transcript, 'audio_duration', None),
            "word_count": len(transcript.text.split()) if transcript.text else 0,
            "original_filename": file.filename or "recording.webm",
            "message": "Audio transcription completed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"Transcription failed: {str(e)}"
        print(f"Transcription exception: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Failed to transcribe audio: {error_detail}")
# Day 7: Echo Bot v2 endpoint (transcribe and TTS)
@app.post("/tts/echo")
async def tts_echo(file: UploadFile = File(...), voice_id: str = Form("en-US-julia")):
    """Echo Bot v2: Transcribe audio and return Murf-generated voice audio URL"""
    try:
        print("=== ECHO BOT START ===")
        print(f"Received file: {file.filename}")
        # Step 1 — Read audio
        audio_data = await file.read()
        if not audio_data:
            raise HTTPException(status_code=400, detail="Empty audio file received")
        # Step 2 — Transcribe with AssemblyAI
        if not ASSEMBLYAI_API_KEY or ASSEMBLYAI_API_KEY == "YOUR_ASSEMBLYAI_API_KEY":
            raise HTTPException(status_code=500, detail="AssemblyAI API key not configured")
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_data)
        if transcript.status == aai.TranscriptStatus.error:
            raise HTTPException(status_code=500, detail=f"Transcription failed: {transcript.error}")
        transcribed_text = transcript.text.strip()
        print(f"Transcribed text: {transcribed_text}")
        if not transcribed_text:
            raise HTTPException(status_code=400, detail="No speech detected in the audio")
        # Step 3 — Send to Murf API
        if not MURF_API_KEY or MURF_API_KEY == "YOUR_MURF_API_KEY":
            raise HTTPException(status_code=500, detail="Murf API key not configured")
        headers = {
            "api-key": MURF_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "text": transcribed_text,
            "voiceId": voice_id,
            "format": "MP3",
            "channelType": "MONO",
            "sampleRate": 44100
        }
        murf_resp = requests.post(MURF_API_URL, json=data, headers=headers)
        if murf_resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Murf API error: {murf_resp.text}")
        murf_result = murf_resp.json()
        audio_url = murf_result.get("audioFile")
        if not audio_url:
            raise HTTPException(status_code=500, detail="No audio URL returned from Murf")
        print(f"Generated Murf audio: {audio_url}")
        print("=== ECHO BOT END ===")
        return {
            "success": True,
            "transcript": transcribed_text,
            "audio_url": audio_url
        }
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"Echo bot processing failed: {str(e)}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)

# Day 8: Integrating a Large Language Model (LLM)
import google.generativeai as genai

# Initialize Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️ Warning: Gemini API key not configured")
else:
    print(f"✅ Gemini API key loaded (length: {len(GEMINI_API_KEY)})")
    
    # Configure the Gemini client
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Create the model instance
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini model initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Gemini model: {str(e)}")
        model = None

# Request body model for LLM
class QueryRequest(BaseModel):

    text: str


    # (Day 8 endpoint removed; only Day 9 audio-based endpoint remains)

# Day 9: LLM Audio Query Endpoint
@app.post("/llm/query")
async def llm_query(
    file: UploadFile = File(...),
    voice_id: str = Form("en-US-julia")
):
    """
    Accepts audio, transcribes it, sends transcript to LLM, then TTS with Murf.
    Returns the generated audio file URL.
    """
    try:
        # 1. Transcribe audio
        audio_data = await file.read()
        if not audio_data:
            raise HTTPException(status_code=400, detail="Empty audio file received")
        if not ASSEMBLYAI_API_KEY or ASSEMBLYAI_API_KEY == "YOUR_ASSEMBLYAI_API_KEY":
            raise HTTPException(status_code=500, detail="AssemblyAI API key not configured")
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_data)
        if transcript.status == aai.TranscriptStatus.error:
            raise HTTPException(status_code=500, detail=f"Transcription failed: {transcript.error}")
        transcribed_text = transcript.text.strip()
        if not transcribed_text:
            raise HTTPException(status_code=400, detail="No speech detected in the audio")

        # 2. Send transcript to LLM
        llm_response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=transcribed_text
        )

        llm_text = getattr(llm_response, "text", None)
        if not llm_text:
            llm_text = str(llm_response)
        llm_text = llm_text.strip()
        print("Gemini LLM response:", repr(llm_text))


        # 3. Murf TTS (handle >3000 chars)
        murf_audio_urls = []
        max_chars = 3000
        for i in range(0, len(llm_text), max_chars):
            chunk = llm_text[i:i+max_chars]
            headers = {
                "api-key": MURF_API_KEY,
                "Content-Type": "application/json"
            }
            data = {
                "text": chunk,
                "voiceId": voice_id,
                "format": "MP3",
                "channelType": "MONO",
                "sampleRate": 44100
            }
            murf_resp = requests.post(MURF_API_URL, json=data, headers=headers)
            if murf_resp.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Murf API error: {murf_resp.text}")
            murf_result = murf_resp.json()
            audio_url = murf_result.get("audioFile")
            if not audio_url:
                raise HTTPException(status_code=500, detail="No audio URL returned from Murf")
            murf_audio_urls.append(audio_url)

        # 4. Return the first audio URL (or all, if you want to concatenate on the client)
        return {
            "success": True,
            "transcript": transcribed_text,
            "llm_response": llm_text,
            "audio_urls": murf_audio_urls
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM audio query failed: {str(e)}")

@app.post("/agent/chat/{session_id}")
async def agent_chat(
    session_id: str,
    file: UploadFile = File(...),
    voice_id: str = Form("en-US-julia")
):
    try:
        # 1. Transcribe audio (STT)
        audio_data = await file.read()
        if not audio_data:
            raise HTTPException(status_code=400, detail="Empty audio file received")
        
        try:
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(audio_data)
            if transcript.status == aai.TranscriptStatus.error:
                raise Exception(f"Transcription failed: {transcript.error}")
            user_text = transcript.text.strip()
        except Exception as e:
            print(f"STT Error: {str(e)}")
            fallback_text = FALLBACK_MESSAGES["STT_ERROR"]
            fallback_audio = await generate_murf_audio(fallback_text, voice_id)
            return {
                "success": False,
                "error": "stt_error",
                "message": "Speech-to-text failed",
                "fallback_response": fallback_text,
                "fallback_audio": fallback_audio
            }

        # 2. Call LLM
        try:
            if not model:
                raise Exception("Gemini model not initialized")
                
            history = chat_history_store.setdefault(session_id, [])
            history.append({"role": "user", "content": user_text})
            context_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history])
            
            llm_response = model.generate_content(context_text)
            llm_text = getattr(llm_response, "text", None) or str(llm_response)
            llm_text = llm_text.strip()
            history.append({"role": "assistant", "content": llm_text})
        except Exception as e:
            print(f"LLM Error: {str(e)}")
            fallback_text = FALLBACK_MESSAGES["LLM_ERROR"]
            fallback_audio = await generate_murf_audio(fallback_text, voice_id)
            return {
                "success": False,
                "error": "llm_error",
                "message": "Language model failed",
                "fallback_response": fallback_text,
                "fallback_audio": fallback_audio
            }

        # 3. Text-to-speech
        try:
            murf_audio_urls = []
            max_chars = 3000
            for i in range(0, len(llm_text), max_chars):
                chunk = llm_text[i:i+max_chars]
                headers = {
                    "api-key": MURF_API_KEY,
                    "Content-Type": "application/json"
                }
                data = {
                    "text": chunk,
                    "voiceId": voice_id,
                    "format": "MP3",
                    "channelType": "MONO",
                    "sampleRate": 44100
                }
                murf_resp = requests.post(MURF_API_URL, json=data, headers=headers)
                if murf_resp.status_code != 200:
                    raise Exception(f"Murf API error: {murf_resp.text}")
                audio_url = murf_resp.json().get("audioFile")
                if not audio_url:
                    raise Exception("No audio URL returned from Murf")
                murf_audio_urls.append(audio_url)
        except Exception as e:
            print(f"TTS Error: {str(e)}")
            return {
                "success": False,
                "error": "tts_error",
                "message": "Text-to-speech failed",
                "fallback_response": FALLBACK_MESSAGES["TTS_ERROR"],
                "fallback_audio": FALLBACK_AUDIO_URL
            }

        return {
            "success": True,
            "session_id": session_id,
            "user_transcript": user_text,
            "assistant_response": llm_text,
            "audio_urls": murf_audio_urls
        }

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "error": "generic_error",
            "message": str(e),
            "fallback_response": FALLBACK_MESSAGES["GENERIC_ERROR"],
            "fallback_audio": FALLBACK_AUDIO_URL
        }

FALLBACK_MESSAGES = {
    "STT_ERROR": "I couldn't understand the audio. Could you try speaking again?",
    "LLM_ERROR": "I'm having trouble thinking right now. Could you try again in a moment?",
    "TTS_ERROR": "I understood you, but I'm having trouble speaking right now. Please try again.",
    "GENERIC_ERROR": "I'm having trouble connecting right now. Please try again."
}
