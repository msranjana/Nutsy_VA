FALLBACK_MESSAGES = {
    "STT_ERROR": "I couldn't understand the audio. Could you try speaking again?",
    "LLM_ERROR": "I'm having trouble thinking right now. Could you try again in a moment?",
    "TTS_ERROR": "I understood you, but I'm having trouble speaking right now. Please try again.",
    "GENERIC_ERROR": "I'm having trouble connecting right now. Please try again."
}

# Update fallback audio URLs to use local files
FALLBACK_AUDIO_URLS = {
    "STT_ERROR": "/static/audio/stt_error.mp3",
    "LLM_ERROR": "/static/audio/llm_error.mp3",
    "TTS_ERROR": "/static/audio/tts_error.mp3",
    "GENERIC_ERROR": "/static/audio/generic_error.mp3"
}