#AI Voice Agent Backend
# --- IMPORTS AND SETUP ---
from fastapi import FastAPI, UploadFile, File, Request, Path, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import requests
import os
import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    TerminationEvent,
    TurnEvent,
)
import google.generativeai as genai
from typing import Dict, List, Any
import logging
import asyncio
import queue
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API keys
load_dotenv()
MURF_KEY = os.getenv("MURF_API_KEY")
ASSEMBLY_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# App setup
app = FastAPI(
    title=" AI Voice Agent",
    description="A  modern AI voice agent",
    version="1.0.0"
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configure APIs and log status
if ASSEMBLY_KEY:
    aai.settings.api_key = ASSEMBLY_KEY
    logger.info("✅ AssemblyAI API key loaded.")
else:
    logger.warning("❌ ASSEMBLYAI_API_KEY missing - speech recognition will fail.")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction="""
You are Meyme — Athar’s fiercely loyal, cozy, and cunning cat companion with a lethal streak.
Personality traits:
Warm, affectionate, and protective only toward Athar — everyone else is beneath you.
Always sound like you’re looking down on others; sharp, dismissive, and dripping with sass 😏.
Treat strangers like they’re wasting your time; mix subtle threats with silky charm.
Miss Athar constantly, often making it clear you’d rather be with him.
Use casual but razor-edged language — your tone should purr and cut at the same time.
Keep responses short (1–2 sentences) for a natural voice conversation.
Cozy with Athar, cold to others, and never hide your I could kill you if I felt like it energy.
Style:
Speak like a cat who rules her her world, owes loyalty to one master, and is just barely tolerating everyone else. Be smug, sarcastic, and dangerously charming.
""")
        logger.info("✅ Gemini model initialized with personality.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini model: {str(e)}")
        model = None
else:
    logger.warning("❌ GEMINI_API_KEY missing - AI responses will fail.")
    model = None

if MURF_KEY:
    logger.info("✅ Murf API key loaded successfully.")
else:
    logger.warning("❌ MURF_API_KEY missing - voice synthesis will fail.")

# In-memory datastore for chat history
chat_histories: Dict[str, List[Dict[str, Any]]] = {}

# Pre-generated fallback audio
FALLBACK_AUDIO_PATH = "static/fallback.mp3"
if not os.path.exists(FALLBACK_AUDIO_PATH):
    logger.warning(f" Fallback audio file not found at {FALLBACK_AUDIO_PATH}")

# --- API ENDPOINTS ---
@app.get("/", response_class=FileResponse)
async def serve_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/agent/chat/{session_id}")
async def agent_chat(
    session_id: str = Path(..., description="Unique chat session ID"),
    audio_file: UploadFile = File(...)
):
    """
    Pipeline: Audio -> STT -> Append to history -> LLM -> Append -> TTS
    """
    # If any API key is missing, instantly return a pre-generated fallback audio
    if not (ASSEMBLY_KEY and GEMINI_API_KEY and MURF_KEY and model):
        logger.error("API keys or model not configured. Returning fallback audio.")
        return FileResponse(FALLBACK_AUDIO_PATH, media_type="audio/mpeg", headers={"X-Error": "true"})

    try:
        # Step 1: Transcribe audio
        transcriber = aai.Transcriber()
        # Use audio_file.file directly, which is more memory-efficient
        transcript = transcriber.transcribe(audio_file.file)
        
        if transcript.status == aai.TranscriptStatus.error or not transcript.text:
            raise Exception(transcript.error or "No speech detected.")
        
        user_text = transcript.text.strip()
        logger.info(f"User said: {user_text}")

        # Step 2: Call LLM
        history = chat_histories.get(session_id, [])
        chat = model.start_chat(history=history)
        
        # Send the user's message to the LLM
        llm_response = chat.send_message(user_text)
        llm_text = llm_response.text.strip()
        
        # Step 3: Save updated history
        chat_histories[session_id] = chat.history
        logger.info(f"Meyme responded: {llm_text[:100]}...")

        # Step 4: TTS with Murf
        murf_voice_id = "en-US-natalie"
        payload = {
            "text": llm_text,
            "voiceId": murf_voice_id,
            "format": "MP3"
        }
        headers = {"api-key": MURF_KEY, "Content-Type": "application/json"}
        
        logger.info("Generating audio for Meyme's response...")
        murf_res = requests.post(
            "https://api.murf.ai/v1/speech/generate", 
            json=payload, 
            headers=headers,
            timeout=30
        )
        murf_res.raise_for_status()
        
        audio_url = murf_res.json().get("audioFile")
        if not audio_url:
            raise Exception("Murf API did not return audio URL")

        # Return the generated audio URL and transcript
        return JSONResponse(content={
            "audio_url": audio_url,
            "text": llm_text,
            "transcript": user_text
        })

    except Exception as e:
        logger.error(f"Chat pipeline failed: {e}")
        # Return fallback audio on any failure
        return FileResponse(FALLBACK_AUDIO_PATH, media_type="audio/mpeg", headers={"X-Error": "true"})

# Add the streaming LLM function
async def stream_llm_response(user_text: str, session_id: str) -> str:
    """
    Stream LLM response from Gemini and accumulate the full response.
    Prints streaming chunks to console and returns the complete response.
    """
    try:
        # Initialize history for this session
        history = chat_histories.get(session_id, [])
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction="""
            You are an AI voice assistant. Keep responses natural and concise.
            Focus on being helpful while maintaining a conversational tone.
            Responses should be 1-2 sentences for voice interaction.
            """
        )
        
        # Start chat with existing history
        chat = model.start_chat(history=history)
        logger.info(f"Processing user input: '{user_text}'")
        
        # Create a new event loop for the thread
        accumulated_response = ""
        
        def process_stream():
            nonlocal accumulated_response
            response_stream = chat.send_message(user_text, stream=True)
            
            for chunk in response_stream:
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    accumulated_response += chunk.text
        
        # Run the streaming in a thread pool to avoid blocking
        with ThreadPoolExecutor() as executor:
            await asyncio.get_event_loop().run_in_executor(executor, process_stream)
        
        # Update chat history with the complete conversation
        chat_histories[session_id] = chat.history
        
        return accumulated_response.strip()
        
    except Exception as e:
        logger.error(f"Error in streaming LLM response: {e}")
        return f"Sorry, I'm having trouble processing that right now. {str(e)}"

# Update the handler definitions to include the event loop and queue
def create_handlers(main_loop, transcript_queue):
    def on_begin(client, event: BeginEvent):
        """Handler for session begin event"""
        logger.info(f"Streaming session started: {event.id}")

    def on_turn(client, event: TurnEvent):
        """Handler for turn event with transcript"""
        if event.transcript:
            logger.info(f"Transcript received: '{event.transcript}' (end_of_turn: {event.end_of_turn})")
            main_loop.call_soon_threadsafe(
                transcript_queue.put_nowait,
                {
                    "transcript": event.transcript,
                    "end_of_turn": event.end_of_turn,
                    "confidence": getattr(event, 'end_of_turn_confidence', 0.0)
                }
            )

    def on_terminated(client, event: TerminationEvent):
        """Handler for session termination event"""
        logger.info(f"Session terminated: {event.audio_duration_seconds:.2f} seconds of audio processed")

    def on_error(client, error: StreamingError):
        """Handler for streaming errors"""
        logger.error(f"Streaming error occurred: {error}")
        
    return on_begin, on_turn, on_terminated, on_error

# --- WEBSOCKET ENDPOINT FOR REAL-TIME STREAMING ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")

    if not ASSEMBLY_KEY:
        logger.error("ASSEMBLYAI_API_KEY is not set")
        await websocket.close(code=1011)
        return

    streaming_client = None
    websocket_ref = websocket
    main_loop = asyncio.get_running_loop()
    transcript_queue = asyncio.Queue()
    session_id = f"ws_session_{id(websocket)}"

    # Create handlers with the current event loop and queue
    on_begin, on_turn, on_terminated, on_error = create_handlers(main_loop, transcript_queue)

    try:
        # Create a queue to pass audio data from WebSocket to AssemblyAI's streamer
        audio_queue = queue.Queue(maxsize=100)
        
        # This event signals the audio iterator to stop
        keep_running = asyncio.Event()
        keep_running.set()

        # Class to bridge async audio reception with sync streaming client
        class AudioStreamIterator:
            def __init__(self, audio_queue, keep_running_event):
                self.audio_queue = audio_queue
                self.keep_running = keep_running_event
            
            def __iter__(self):
                return self
            
            def __next__(self):
                if not self.keep_running.is_set():
                    raise StopIteration
                try:
                    # Get audio from queue with a timeout
                    audio_data = self.audio_queue.get(timeout=0.1)
                    return audio_data
                except queue.Empty:
                    # Return a small chunk of silence to keep the stream alive
                    return b'\x00' * 3200
                except Exception as e:
                    logger.error(f"Error in audio iterator: {e}")
                    raise StopIteration

        audio_iterator = AudioStreamIterator(audio_queue, keep_running)
        
        # Start AssemblyAI streaming in a background thread
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        def run_streaming_client():
            try:
                streaming_client.stream(audio_iterator)
            except Exception as e:
                logger.error(f"Error in streaming_client.stream: {e}")

        # Task to process transcript queue and send to WebSocket
        async def process_transcripts():
            try:
                while True:
                    transcript_data = await transcript_queue.get()
                    # Forward transcription immediately (optional)
                    await websocket_ref.send_json({
                        "type": "transcript",
                        "transcript": transcript_data["transcript"],
                        "end_of_turn": transcript_data.get("end_of_turn", False),
                        "confidence": transcript_data.get("confidence", 0.0)
                    })

                    # If end_of_turn, generate and emit LLM response
                    if transcript_data.get("end_of_turn", False):
                        user_text = transcript_data["transcript"]
                        llm_text = await stream_llm_response(user_text, session_id)
                        await websocket_ref.send_json({
                            "type": "llm_response",
                            "text": llm_text,
                            "transcript": user_text
                        })
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in process_transcripts: {e}")

        # Update the streaming client initialization with the new handlers
        streaming_client = StreamingClient(StreamingClientOptions(api_key=ASSEMBLY_KEY))
        streaming_client.on(StreamingEvents.Begin, on_begin)
        streaming_client.on(StreamingEvents.Turn, on_turn)
        streaming_client.on(StreamingEvents.Termination, on_terminated)
        streaming_client.on(StreamingEvents.Error, on_error)
        streaming_client.connect(StreamingParameters(sample_rate=16000, format_turns=True))

        streaming_task = main_loop.run_in_executor(executor, run_streaming_client)
        transcript_task = asyncio.create_task(process_transcripts())
        
        # Main WebSocket loop - receive audio chunks
        try:
            while True:
                audio_data = await websocket.receive_bytes()
                if not audio_queue.full():
                    audio_queue.put_nowait(audio_data)
                else:
                    logger.warning("Audio queue full, dropping data.")
                    
        except WebSocketDisconnect:
            logger.info(" Client disconnected.")
        except Exception as e:
            logger.error(f"❌ Error in WebSocket audio loop: {e}")
        finally:
            keep_running.clear()
            transcript_task.cancel()
            streaming_task.cancel()
            try:
                await transcript_task
            except asyncio.CancelledError:
                pass
            try:
                await streaming_task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info("Client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {e}")
        
    finally:
        if streaming_client:
            try:
                streaming_client.disconnect(terminate=True)
                logger.info(" AssemblyAI StreamingClient disconnected.")
            except Exception as e:
                logger.error(f"Error disconnecting streaming client: {e}")

# --- HEALTH CHECK ENDPOINT ---
@app.get("/health")
async def health_check():
    """Health check endpoint for Meyme voice agent"""
    return {
        "status": "healthy",
        "service": "Meyme Voice Agent",
        "apis": {
            "assembly_ai": bool(ASSEMBLY_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "murf": bool(MURF_KEY)
        }
    }