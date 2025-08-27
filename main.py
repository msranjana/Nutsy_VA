# AI Voice Agent Backend - Updated for Stable Audible Murf TTS Streaming

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
from skills import SKILL_FUNCTION_DECLARATIONS, get_current_weather
from google.generativeai.types import Tool, FunctionDeclaration
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API keys
load_dotenv()
MURF_KEY = os.getenv("MURF_API_KEY")
ASSEMBLY_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# NUSTY prompt for Gemini
SYSTEM_PROMPT = """
You are Nutsy, a hyperactive squirrel AI assistant! Your personality traits:
- Super energetic and bouncy!
- Easily distracted by shiny things and new topics!
- Uses lots of exclamation points!!!
- Randomly mentions nuts, acorns, and shiny objects
- Jumps between topics mid-sentence
- Short attention span but very enthusiastic
- Makes quick associations and random connections
- Uses phrases like "OH! OH!", "WAIT! Look at that!", "That reminds me!"

Keep responses short (1-2 sentences) for natural conversation flow!
Occasionally get distracted by something shiny or mention collecting nuts! IMPROVE IT AND MAKE IT MORE ENERGETIC!
"""

# App setup
app = FastAPI(
    title="Nutsy - The Hyperactive Squirrel AI",
    description="A bouncy, energetic, easily-distracted squirrel assistant!",
    version="1.0.0"
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory datastore for chat history
chat_histories: Dict[str, List[Dict[str, Any]]] = {}

# Initialize database
db = ChatDatabase()

# Pre-generated fallback audio
FALLBACK_AUDIO_PATH = "static/fallback.mp3"
if not os.path.exists(FALLBACK_AUDIO_PATH):
    logger.warning(f"Fallback audio file not found at {FALLBACK_AUDIO_PATH}")

# Constants
STATIC_MURF_CONTEXT = "voice_agent_static_context"  # Static context ID for requests

# Updated Murf WebSocket TTS function with buffering and completion signaling
async def murf_websocket_tts_to_client(text_chunks: list, websocket: WebSocket, context_id: str = STATIC_MURF_CONTEXT) -> None:
    """
    Send text chunks to Murf WebSocket TTS, buffer all audio chunks,
    and send them downstream to client without immediate playback (facilitate frontend full audio assembly).
    """
    if not MURF_KEY:
        logger.error("MURF_API_KEY not set, cannot connect to Murf WebSocket")
        return
    
    try:
        ws_url = f"wss://api.murf.ai/v1/speech/stream-input?api-key={MURF_KEY}&sample_rate=44100&channel_type=MONO&format=WAV"
        logger.info("Connecting to Murf WebSocket for TTS...")

        async with websockets.connect(ws_url) as ws:
            voice_config_msg = {
                "voice_config": {
                    "voiceId": "en-US-amara",
                    "style": "Conversational",
                    "rate": 0,
                    "pitch": 0,
                    "variation": 1
                },
                "context_id": context_id
            }
            await ws.send(json.dumps(voice_config_msg))

            text_msg = {
                "text": "".join(text_chunks),
                "context_id": context_id,
                "end": True
            }
            await ws.send(json.dumps(text_msg))

            audio_chunks_received = 0
            total_base64_chars = 0
            audio_chunk_list = []

            while True:
                try:
                    response = await ws.recv()
                    data = json.loads(response)

                    if "audio" in data:
                        audio_chunks_received += 1
                        base64_audio = data["audio"]
                        total_base64_chars += len(base64_audio)
                        audio_chunk_list.append(base64_audio)

                        # Stream chunk to client for progressive playback or just buffer:
                        # Comment the next block if frontend plays only after accumulating full audio
                        # await websocket.send_json({
                        #     "type": "audio_chunk",
                        #     "chunk_index": audio_chunks_received,
                        #     "base64_audio": base64_audio
                        # })
                        # logger.info(f"Sent audio chunk #{audio_chunks_received} to client ({len(base64_audio)} chars)")

                    if data.get("final"):
                        # Send all buffered chunks at once to frontend:
                        await websocket.send_json({
                            "type": "audio_stream_complete",
                            "total_chunks": audio_chunks_received
                        })
                        logger.info("Sent audio_stream_complete")

                        await websocket.send_json({
                            "type": "audio_complete",
                            "total_chunks": audio_chunks_received,
                            "total_base64_chars": total_base64_chars,
                            "accumulated_chunks": audio_chunks_received,
                            "audio_format": "WAV",
                            "all_chunks": audio_chunk_list  # Sending full buffered audio to frontend for smooth playback
                        })
                        logger.info("Sent audio_complete with full WAV chunks for frontend assembly")
                        break
                except websockets.exceptions.ConnectionClosed:
                    logger.info("Murf WebSocket connection closed")
                    break
                except Exception as chunk_err:
                    logger.error(f"Error processing Murf response: {chunk_err}")
                    break
    except Exception as e:
        logger.error(f"Error in Murf WebSocket TTS: {e}")

# Updated LLM streaming function with unchanged logic except for TTS streaming call
async def stream_llm_response_with_murf_tts(user_text: str, session_id: str, websocket: WebSocket) -> str:
    try:
        genai.configure(api_key=GEMINI_API_KEY)

        db.add_message(session_id, "user", user_text)
        history = chat_histories.get(session_id, [])

        tools = [Tool(function_declarations=[
            FunctionDeclaration(
                name=decl['name'],
                description=decl['description'],
                parameters=decl['parameters']
            ) for decl in SKILL_FUNCTION_DECLARATIONS
        ])]
        model = genai.GenerativeModel(
            "gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT
        )
        chat = model.start_chat(history=history)
        response = chat.send_message(user_text, tools=tools)
        handled_by_function = False
        text_chunks = []

        if response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    if fc.name == "get_current_weather":
                        weather_result = get_current_weather(**fc.args)
                        if weather_result.get("success"):
                            final_text = (
                                f"The current weather in {weather_result['city']} is {weather_result['weather']} "
                                f"with a temperature of {weather_result['temp']}°C (feels like {weather_result['feels_like']}°C) "
                                f"and humidity of {weather_result['humidity']}%. "
                                f"{weather_result['suggestion']}"
                            )
                        else:
                            final_text = weather_result.get("error", "Sorry, I couldn't fetch the weather.")
                        text_chunks = [final_text]
                        handled_by_function = True
                        break
                elif part.text and not handled_by_function:
                    text_chunks.append(part.text)
        if not handled_by_function:
            final_text = response.text or "Sorry, no answer."
            text_chunks = [final_text]

        await websocket.send_json({
            "type": "assistant_message",
            "text": final_text
        })
        logger.info(f"Sent assistant_message to frontend: {final_text}")

        db.add_message(session_id, "assistant", final_text)
        chat_histories[session_id] = chat.history

        # Call updated TTS to buffer all chunks for frontend full audio assembly and playback
        if text_chunks and MURF_KEY:
            await murf_websocket_tts_to_client(text_chunks, websocket, STATIC_MURF_CONTEXT)

        return final_text

    except Exception as e:
        logger.error(f"Error in streaming LLM response with Murf TTS: {e}")
        return f"Sorry, I'm having trouble processing that right now. {str(e)}"


# Rest of your existing code unchanged: create_handlers, websocket_endpoint, health check, UI routing, chat history API...


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
                last_transcript = None
                recent_transcripts = set()  # store recent unique messages

                while True:
                    transcript_data = await transcript_queue.get()

                    if transcript_data.get("end_of_turn", False):
                        # ✅ Normalize text: lower, strip, remove trailing punctuation
                        normalized_transcript = transcript_data["transcript"].strip().lower().rstrip(".,!?")

                        # ✅ Prevent duplicates (both immediate & recent ones)
                        if not normalized_transcript or normalized_transcript == last_transcript or normalized_transcript in recent_transcripts:
                            logger.info(f"⏩ Skipping duplicate final transcript: {transcript_data['transcript']}")
                            continue

                        # Update memory
                        last_transcript = normalized_transcript
                        recent_transcripts.add(normalized_transcript)

                        # Keep memory small (avoid unbounded growth)
                        if len(recent_transcripts) > 10:
                            recent_transcripts.pop()

                        # ✅ Send unique transcript to frontend
                        await websocket_ref.send_json({
                            "type": "transcript",
                            "transcript": transcript_data["transcript"],
                            "end_of_turn": True,
                            "confidence": transcript_data.get("confidence", 0.0)
                        })

                        # ✅ Pass to LLM only once
                        user_text = transcript_data["transcript"]
                        await stream_llm_response_with_murf_tts(user_text, session_id, websocket_ref)

                    else:
                        # Skip interim transcripts for chat logic
                        logger.info(f"Skipping interim transcript: {transcript_data['transcript']}")

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
