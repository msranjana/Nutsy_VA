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

async function startRecording() {
    console.log('🎤 Starting recording...');
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            console.log('🛑 Recording stopped, processing audio...');
            audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            audioURL = URL.createObjectURL(audioBlob);
            await processLLMAudioBot();
        };

        mediaRecorder.start();
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
            console.log('👤 User said:', result.user_transcript);
            console.log('🤖 Bot replied:', result.assistant_response);
            
            appendMessage('user', result.user_transcript);
            appendMessage('ai', result.assistant_response);

            if (result.audio_urls && result.audio_urls.length > 0) {
                console.log('🔊 Playing bot response audio...');
                const audio = new Audio(result.audio_urls[0]);
                audio.onended = () => {
                    console.log('🔄 Bot response finished, starting new recording...');
                    startRecording();
                };
                audio.play();
            }
        } else {
            console.error('❌ Server processing failed:', result);
        }
    } catch (error) {
        console.error('❌ Error in LLM Audio Bot:', error);
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
});