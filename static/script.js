const FALLBACK_MESSAGES = {
    STT_ERROR: "I couldn't understand the audio. Could you try speaking again?",
    LLM_ERROR: "I'm having trouble thinking right now. Could you try again in a moment?",
    TTS_ERROR: "I understood you, but I'm having trouble speaking right now. Please try again.",
    GENERIC_ERROR: "I'm having trouble connecting right now. Please try again."
};

const FALLBACK_AUDIO_URLS = {
    STT_ERROR: "/static/audio/stt_error.mp3",
    LLM_ERROR: "/static/audio/llm_error.mp3", 
    TTS_ERROR: "/static/audio/tts_error.mp3",
    GENERIC_ERROR: "/static/audio/generic_error.mp3"
};

if (!window.sessionStorage.getItem("session_id")) {
    const newSessionId = crypto.randomUUID();
    window.sessionStorage.setItem("session_id", newSessionId);
    const url = new URL(window.location.href);
    url.searchParams.set("session_id", newSessionId);
    window.history.replaceState({}, "", url);
}
const sessionId = window.sessionStorage.getItem("session_id");

function appendMessage(role, text) {
    console.log(`💬 Appending ${role} message:`, text);
    const chatHistory = document.getElementById('chatHistory');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    
    // Add prefix based on role
    const prefix = role === 'user' ? 'You: ' : 'BOT: ';
    messageDiv.textContent = `${prefix}${text}`;
    
    chatHistory.appendChild(messageDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// No legacy TTS functionality needed

// Echo Bot Recording Functionality
let mediaRecorder;
let audioChunks = [];
let audioBlob;
let audioURL;

let socket;

// Initialize WebSocket connection
function initWebSocket() {
    socket = new WebSocket("ws://localhost:8000/ws");
    
    socket.onopen = () => {
        console.log("🌐 WebSocket connected");
    };
    
    socket.onclose = () => {
        console.log("🔌 WebSocket disconnected");
        // Attempt to reconnect after 3 seconds
        setTimeout(initWebSocket, 3000);
    };
    
    socket.onerror = (error) => {
        console.error("❌ WebSocket error:", error);
    };
}

async function startRecording() {
    console.log('🎤 Starting recording...');
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
        audioChunks = [];

        // WebSocket streaming setup
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            initWebSocket();
        }

        mediaRecorder.ondataavailable = (event) => {
            // Store chunks for local processing
            audioChunks.push(event.data);
            
            // Stream to WebSocket if connected
            if (event.data.size > 0 && socket && socket.readyState === WebSocket.OPEN) {
                event.data.arrayBuffer().then(buffer => {
                    socket.send(buffer);
                }).catch(error => {
                    console.error("❌ Error converting to buffer:", error);
                });
            }
        };

        mediaRecorder.onstop = async () => {
            console.log('🛑 Recording stopped, processing audio...');
            audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            audioURL = URL.createObjectURL(audioBlob);
            await processLLMAudioBot();
            
            // Close WebSocket connection
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.close();
            }
        };

        mediaRecorder.start(250); // Send chunks every 250ms
        updateRecordingUI(true);
        console.log('✅ Recording started successfully');
    } catch (error) {
        console.error('❌ Error starting recording:', error);
    }
}

async function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
    
    mediaRecorder.stop();
    if (mediaRecorder.stream) {
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
    updateRecordingUI(false);
    
    // Close WebSocket connection
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
    }
}

function updateRecordingUI(isRecording) {
    const startBtn = document.getElementById('startRecording');
    const stopBtn = document.getElementById('stopRecording');

    if (startBtn) startBtn.disabled = isRecording;
    if (stopBtn) stopBtn.disabled = !isRecording;
}

async function processLLMAudioBot() {
    try {
        console.log('🤖 Processing audio with LLM Bot...');
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');
        formData.append('voice_id', 'en-US-julia');

        console.log('📤 Sending audio to server...');
        const response = await fetch(`/agent/chat/${sessionId}`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        console.log('📥 Received response:', result);

        if (result.success) {
            console.log('🎯 Successfully processed audio');
            appendMessage('user', result.user_transcript);
            appendMessage('ai', result.assistant_response);

            if (result.audio_urls && result.audio_urls.length > 0) {
                console.log('🔊 Playing bot response audio...');
                playAudioResponse(result.audio_urls[0]);
            }
        } else {
            console.error('❌ Error:', result.error);
            appendMessage('system', result.fallback_response);
            
            if (result.fallback_audio) {
                console.log('🔊 Playing fallback audio...');
                playAudioResponse(result.fallback_audio);
            }
        }
    } catch (error) {
        console.error('❌ Critical error:', error);
        appendMessage('system', FALLBACK_MESSAGES.GENERIC_ERROR);
        playAudioResponse(FALLBACK_AUDIO_URL);
    }
}

function playAudioResponse(audioUrl) {
    try {
        const audio = new Audio(audioUrl);
        audio.onended = () => {
            console.log('🔄 Audio finished, starting new recording...');
            startRecording();
        };
        audio.onerror = (error) => {
            console.error('❌ Audio playback error:', error);
            // If audio fails, still allow new recording
            startRecording();
        };
        audio.play();
    } catch (error) {
        console.error('❌ Audio setup error:', error);
        startRecording();
    }
}

// When sending audio to backend:
async function sendAudio(fileBlob) {
    const formData = new FormData();
    formData.append("file", fileBlob, "query.webm");
    formData.append("voice_id", "en-US-julia");

    try {
        const response = await fetch(`/agent/chat/${sessionId}`, {
            method: "POST",
            body: formData
        });

        const result = await response.json();
        console.log("LLM Result:", result);

        // Display the actual transcribed text instead of [Voice message]
        appendMessage('user', result.user_transcript);
        appendMessage('ai', result.assistant_response);

        // Play assistant's voice output, then auto-record again
        if (result.audio_urls.length > 0) {
            playAndListen(result.audio_urls[0]);
        }
    } catch (error) {
        console.error("Error:", error);
    }
}

// Add this near the top of the file, after sessionId initialization
document.addEventListener('DOMContentLoaded', () => {
    const generateButton = document.querySelector('.generate-button');
    if (generateButton) {
        generateButton.addEventListener('click', async () => {
            const textInput = document.getElementById('textInput');
            const voiceSelect = document.getElementById('voiceSelect');
            
            if (!textInput || !textInput.value.trim()) {
                console.error('No text to generate speech from');
                return;
            }

            try {
                const response = await fetch('/tts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        text: textInput.value.trim(),
                        voice_id: voiceSelect ? voiceSelect.value : 'en-US-julia'
                    })
                });

                const result = await response.json();
                if (result.audio_url) {
                    const audioPlayer = document.getElementById('audioPlayer');
                    if (audioPlayer) {
                        audioPlayer.src = result.audio_url;
                        document.getElementById('audioSection').style.display = 'block';
                    }
                }
            } catch (error) {
                console.error('Error generating speech:', error);
            }
        });
    }
    
    // Initialize WebSocket connection
    initWebSocket();
});

