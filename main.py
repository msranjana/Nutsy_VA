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
import websockets
import json
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from database import ChatDatabase


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Load API keys
load_dotenv()
MURF_KEY = os.getenv("MURF_API_KEY")
ASSEMBLY_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Meyme prompt for Gemini
SYSTEM_PROMPT = """
You are a helpful and friendly AI voice assistant.
Personality traits:
- Warm and welcoming to all users
- Professional but casual tone
- Helpful and encouraging
- Clear and concise responses
- Patient and understanding
Keep responses short (1-2 sentences) for natural voice conversation.
"""

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
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SYSTEM_PROMPT)
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

# Initialize database
db = ChatDatabase()


# Pre-generated fallback audio
FALLBACK_AUDIO_PATH = "static/fallback.mp3"
if not os.path.exists(FALLBACK_AUDIO_PATH):
    logger.warning(f" Fallback audio file not found at {FALLBACK_AUDIO_PATH}")


# --- Murf WebSocket TTS function ---
STATIC_MURF_CONTEXT = "voice_agent_static_context"  # Static context ID for all requests

# --- Murf WebSocket TTS function (updated to stream to client) ---
async def murf_websocket_tts_to_client(text_chunks: list, websocket: WebSocket, context_id: str = STATIC_MURF_CONTEXT) -> None:
    """
    Send streaming text chunks to Murf WebSocket and forward base64 audio chunks over FastAPI websocket.
    """
    if not MURF_KEY:
        logger.error("MURF_API_KEY not set, cannot connect to Murf WebSocket")
        return
    
    try:
        ws_url = f"wss://api.murf.ai/v1/speech/stream-input?api-key={MURF_KEY}&sample_rate=44100&channel_type=MONO&format=WAV"
        logger.info("Connecting to Murf WebSocket for TTS...")
        
        async with websockets.connect(ws_url) as ws:
            # voice config
            voice_config_msg = {
                "voice_config": {
                    "voiceId": "en-US-amara",
                    "style": "Conversational",
                    "rate": 0,
                    "pitch": 0,
                    "variation": 1
                },
                "context_id": STATIC_MURF_CONTEXT
            }
            await ws.send(json.dumps(voice_config_msg))

            # text chunk message
            text_msg = {
                "text": "".join(text_chunks),
                "context_id": STATIC_MURF_CONTEXT,
                "end": True
            }
            await ws.send(json.dumps(text_msg))
            
            audio_chunks_received = 0
            total_base64_chars = 0  # Track total characters

            while True:
                try:
                    response = await ws.recv()
                    data = json.loads(response)

                    if "audio" in data:
                        audio_chunks_received += 1
                        base64_audio = data["audio"]
                        total_base64_chars += len(base64_audio)  # Add to total
                        
                        await websocket.send_json({
                            "type": "audio_chunk",
                            "chunk_index": audio_chunks_received,
                            "base64_audio": base64_audio
                        })
                        logger.info(f"📤 Sent audio chunk #{audio_chunks_received} to client ({len(base64_audio)} chars)")

                    if data.get("final"):
                        # Send stream complete message
                        await websocket.send_json({
                            "type": "audio_stream_complete",
                            "total_chunks": audio_chunks_received
                        })
                        logger.info("✅ Sent audio_stream_complete")

                        # Send final audio complete message with stats
                        await websocket.send_json({
                            "type": "audio_complete",
                            "total_chunks": audio_chunks_received,
                            "total_base64_chars": total_base64_chars,
                            "accumulated_chunks": audio_chunks_received,
                            "audio_format": "WAV"
                        })
                        logger.info("✅ Sent audio_complete for frontend compatibility")
                        break

                except websockets.exceptions.ConnectionClosed:
                    logger.info("🔌 Murf WebSocket connection closed")
                    break
                except Exception as chunk_error:
                    logger.error(f"❌ Error processing Murf response: {chunk_error}")
                    break

    except Exception as e:
        logger.error(f"❌ Error in Murf WebSocket TTS: {e}")


# --- Stream LLM response and send to Murf WebSocket TTS ---
async def stream_llm_response_with_murf_tts(user_text: str, session_id: str, websocket: WebSocket) -> str:
    try:
        # Save user message to database
        db.add_message(session_id, "user", user_text)
        
        history = chat_histories.get(session_id, [])
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT
        )
        chat = model.start_chat(history=history)
        
        # Print request info
        print("\n" + "=" * 60)
        print(f"🔄 LLM REQUEST:")
        print(f"Session: {session_id}")
        print(f"Input: '{user_text}'")
        print("=" * 60)
        
        accumulated_response = ""
        text_chunks = []
        response_stream = chat.send_message(user_text, stream=True)
        
        for chunk in response_stream:
            if chunk.text:
                print(chunk.text, end="", flush=True)
                accumulated_response += chunk.text
                text_chunks.append(chunk.text)
        
        # Print response info
        print("\n" + "=" * 60)
        print(f"✅ LLM RESPONSE:")
        print(f"Full response: '{accumulated_response.strip()}'")
        print(f"API URL: https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash")
        print("=" * 60)
        
        if text_chunks and MURF_KEY:
            # Pass websocket to TTS function
            await murf_websocket_tts_to_client(text_chunks, websocket, STATIC_MURF_CONTEXT)
        
        # Save AI response to database
        full_response = "".join(text_chunks)
        db.add_message(session_id, "assistant", full_response)
        
        chat_histories[session_id] = chat.history
        
        return full_response.strip()
    except Exception as e:
        logger.error(f"Error in streaming LLM response with Murf TTS: {e}")
        return f"Sorry, I'm having trouble processing that right now. {str(e)}"


# Your existing stream_llm_response function (unchanged)
async def stream_llm_response(user_text: str, session_id: str) -> str:
    try:
        history = chat_histories.get(session_id, [])
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction="""
            You are an AI voice assistant. Keep responses natural and concise.
            Focus on being helpful while maintaining a conversational tone.
            Responses should be 1-2 sentences for voice interaction.
            """
        )
        chat = model.start_chat(history=history)
        logger.info(f"Processing user input: '{user_text}'")
        accumulated_response = ""
        def process_stream():
            nonlocal accumulated_response
            response_stream = chat.send_message(user_text, stream=True)
            for chunk in response_stream:
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    accumulated_response += chunk.text
        with ThreadPoolExecutor() as executor:
            await asyncio.get_event_loop().run_in_executor(executor, process_stream)
        chat_histories[session_id] = chat.history
        return accumulated_response.strip()
    except Exception as e:
        logger.error(f"Error in streaming LLM response: {e}")
        return f"Sorry, I'm having trouble processing that right now. {str(e)}"


# Update the handler definitions
def create_handlers(main_loop, transcript_queue):
    def on_begin(client, event: BeginEvent):
        logger.info(f"Streaming session started: {event.id}")

    def on_turn(client, event: TurnEvent):
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
        logger.info(f"Session terminated: {event.audio_duration_seconds:.2f} seconds processed")

    def on_error(client, error: StreamingError):
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

    on_begin, on_turn, on_terminated, on_error = create_handlers(main_loop, transcript_queue)

    try:
        audio_queue = queue.Queue(maxsize=100)
        keep_running = asyncio.Event()
        keep_running.set()

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
                    audio_data = self.audio_queue.get(timeout=0.1)
                    return audio_data
                except queue.Empty:
                    return b'\x00' * 3200
                except Exception as e:
                    logger.error(f"Error in audio iterator: {e}")
                    raise StopIteration

        audio_iterator = AudioStreamIterator(audio_queue, keep_running)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        def run_streaming_client():
            try:
                streaming_client.stream(audio_iterator)
            except Exception as e:
                logger.error(f"Error in streaming_client.stream: {e}")

        async def process_transcripts():
            try:
                while True:
                    transcript_data = await transcript_queue.get()
                    await websocket_ref.send_json({
                        "type": "transcript",
                        "transcript": transcript_data["transcript"],
                        "end_of_turn": transcript_data.get("end_of_turn", False),
                        "confidence": transcript_data.get("confidence", 0.0)
                    })

                    if transcript_data.get("end_of_turn", False):
                        user_text = transcript_data["transcript"]
                        # Pass websocket_ref to the function
                        llm_text = await stream_llm_response_with_murf_tts(user_text, session_id, websocket_ref)
                        await websocket_ref.send_json({
                            "type": "llm_response",
                            "text": llm_text,
                            "transcript": user_text
                        })
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in process_transcripts: {e}")

        streaming_client = StreamingClient(StreamingClientOptions(api_key=ASSEMBLY_KEY))
        streaming_client.on(StreamingEvents.Begin, on_begin)
        streaming_client.on(StreamingEvents.Turn, on_turn)
        streaming_client.on(StreamingEvents.Termination, on_terminated)
        streaming_client.on(StreamingEvents.Error, on_error)
        streaming_client.connect(StreamingParameters(sample_rate=16000, format_turns=True))

        streaming_task = main_loop.run_in_executor(executor, run_streaming_client)
        transcript_task = asyncio.create_task(process_transcripts())

        try:
            while True:
                audio_data = await websocket.receive_bytes()
                if not audio_queue.full():
                    audio_queue.put_nowait(audio_data)
                else:
                    logger.warning("Audio queue full, dropping data.")
        except WebSocketDisconnect:
            logger.info("Client disconnected.")
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
                logger.info("AssemblyAI StreamingClient disconnected.")
            except Exception as e:
                logger.error(f"Error disconnecting streaming client: {e}")


# --- HEALTH CHECK ENDPOINT ---
@app.get("/health")
async def health_check():
    """Health check endpoint for Voice Agent"""
    return {
        "status": "healthy",
        "service": "Voice Agent",
        "apis": {
            "assembly_ai": bool(ASSEMBLY_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "murf": bool(MURF_KEY)
        }
    }

# Add after the imports and before the WebSocket endpoint
@app.get("/")
async def serve_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Add endpoint to fetch chat history
@app.get("/api/history/{session_id}")
async def get_chat_history(session_id: str):
    try:
        history = db.get_session_history(session_id)
        return {"status": "success", "history": history}
    except Exception as e:
        return {"status": "error", "message": str(e)}
