async function generateSpeech() {
    const textInput = document.getElementById('textInput');
    const voiceSelect = document.getElementById('voiceSelect');
    const generateButton = document.querySelector('.generate-button');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const audioSection = document.getElementById('audioSection');
    const audioPlayer = document.getElementById('audioPlayer');
    const audioLength = document.getElementById('audioLength');
    const characterCount = document.getElementById('characterCount');
    
    const text = textInput.value.trim();
    const voiceId = voiceSelect.value;
    
    if (!text) {
        alert('Please enter some text to convert to speech.');
        return;
    }
    
    // Show loading, disable button
    generateButton.disabled = true;
    generateButton.textContent = 'Generating...';
    loadingIndicator.style.display = 'flex';
    audioSection.style.display = 'none';
    
    try {
        const response = await fetch('/tts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                text: text,
                voice_id: voiceId 
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('TTS Response:', result);
            
            if (result.audio_url) {
                // Set up audio player
                audioPlayer.src = result.audio_url;
                audioPlayer.load();
                
                // Update info display
                if (result.audio_length) {
                    audioLength.textContent = `Duration: ${result.audio_length.toFixed(1)}s`;
                }
                if (result.consumed_characters) {
                    characterCount.textContent = `Characters used: ${result.consumed_characters}`;
                }
                
                // Show audio section
                audioSection.style.display = 'block';
                
                // Auto-play the audio
                try {
                    await audioPlayer.play();
                } catch (playError) {
                    console.log('Auto-play prevented by browser:', playError);
                    alert('Audio generated successfully! Click the play button to listen.');
                }
                
            } else {
                alert('Audio URL not received from server');
            }
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to generate audio'}`);
            console.error('API Error:', error);
        }
    } catch (error) {
        console.error('Network Error:', error);
        alert('Failed to connect to the server. Please check your connection and try again.');
    } finally {
        // Reset button and hide loading
        generateButton.disabled = false;
        generateButton.textContent = '🎤 Generate Speech';
        loadingIndicator.style.display = 'none';
    }
}

// Legacy function for backward compatibility
async function tryNow() {
    const text = prompt("Enter text to convert to speech:");
    if (!text) return;
    
    try {
        const response = await fetch('/tts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: text })
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.audio_url) {
                // Create audio element and play
                const audio = new Audio(result.audio_url);
                audio.play();
                alert("Audio generated successfully! Playing now...");
            } else {
                alert("Audio URL not received from server");
            }
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to generate audio'}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Voice agent functionality coming soon! 🎤\n(Please configure your Murf API key first)');
    }
}

function helloWorld() {
    alert("Hello from JavaScript!");
}

// Allow Enter key to submit the form
document.addEventListener('DOMContentLoaded', function() {
    const textInput = document.getElementById('textInput');
    if (textInput) {
        textInput.addEventListener('keydown', function(event) {
            if (event.ctrlKey && event.key === 'Enter') {
                generateSpeech();
            }
        });
    }
});

// Echo Bot Recording Functionality
let mediaRecorder;
let audioChunks = [];
let audioBlob;
let audioURL;

async function startRecording() {
    try {
        console.log('Starting recording...');
        
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        
        mediaRecorder.addEventListener('dataavailable', event => {
            console.log('Data available:', event.data.size);
            audioChunks.push(event.data);
        });
        
        mediaRecorder.addEventListener('stop', async () => {
            console.log('MediaRecorder stopped');
            
            // Create blob from recorded chunks
            audioBlob = new Blob(audioChunks, { type: 'audio/webm;codecs=opus' });
            audioURL = URL.createObjectURL(audioBlob);
            
            console.log('Audio blob created:', audioBlob);
            console.log('Audio URL created:', audioURL);
            
            // Show playback section
            const playbackSection = document.getElementById('playbackSection');
            playbackSection.style.display = 'block';
            
            // Process through LLM Audio Bot (Day 9)
            await processLLMAudioBot();
        });
        
        mediaRecorder.start();
        console.log('MediaRecorder started');
        
        // Update UI
        updateRecordingUI(true);
        
    } catch (error) {
        console.error('Error starting recording:', error);
        showUploadStatus('error', 'Recording Error', 'Could not start recording: ' + error.message);
    }
}

async function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
        console.error('MediaRecorder is not active');
        return;
    }

    console.log('Stopping recording...');
    mediaRecorder.stop();
    
    // Stop all tracks to release the microphone
    if (mediaRecorder.stream) {
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
    
    // Update UI
    updateRecordingUI(false);
}

// Fix: Add the missing updateRecordingUI function
function updateRecordingUI(isRecording) {
    const startBtn = document.getElementById('startRecording');
    const stopBtn = document.getElementById('stopRecording');
    const recordingStatus = document.getElementById('recordingStatus');
    
    if (isRecording) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        recordingStatus.style.display = 'flex';
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        recordingStatus.style.display = 'none';
    }
}

async function processLLMAudioBot() {
    try {
        const playbackAudio = document.getElementById('playbackAudio');
        const voiceSelect = document.getElementById('voiceSelect');
        const selectedVoice = voiceSelect ? voiceSelect.value : 'en-US-julia';

        playbackAudio.style.opacity = '0.5';
        showUploadStatus('uploading', 'Processing...', 'Transcribing, LLM, and generating speech...');

        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');
        formData.append('voice_id', selectedVoice);

        const response = await fetch('/llm/query', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(`LLM Audio Bot failed: ${response.status} - ${errorData.detail || 'Unknown error'}`);
        }

        const result = await response.json();
        console.log('LLM Audio Bot response:', result);

        if (result.success && result.audio_urls && result.audio_urls.length > 0) {
            playbackAudio.src = result.audio_urls[0];
            playbackAudio.style.opacity = '1';
            if (result.llm_response) {
                showTranscriptionResult(result.llm_response);
            }
            try {
                await playbackAudio.play();
                showUploadStatus('success', 'LLM Audio Bot Complete!', 'LLM response generated and played.');
            } catch (playError) {
                showUploadStatus('success', 'LLM Audio Bot Complete!', 'Click play to hear the AI-generated response.');
            }
        } else {
            throw new Error('No audio URL returned from LLM Audio Bot');
        }
    } catch (error) {
        console.error('LLM Audio Bot error:', error);
        const playbackAudio = document.getElementById('playbackAudio');
        playbackAudio.style.opacity = '1';
        showUploadStatus('error', 'LLM Audio Bot Failed', error.message);
    }
}

async function processEchoBotV2() {
    try {
        const playbackAudio = document.getElementById('playbackAudio');
        const voiceSelect = document.getElementById('voiceSelect');
        
        // Show loading state
        playbackAudio.style.opacity = '0.5';
        showUploadStatus('uploading', 'Processing...', 'Transcribing and generating speech...');
        
        // Get selected voice (or default)
        const selectedVoice = voiceSelect ? voiceSelect.value : 'en-US-julia';
        
        // Prepare form data
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');
        formData.append('voice_id', selectedVoice);
        
        console.log('Sending to Echo Bot v2 endpoint...');
        console.log('Selected voice:', selectedVoice);
        
        // Send to Echo Bot v2 endpoint
        const response = await fetch('/tts/echo', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(`Echo Bot v2 failed: ${response.status} - ${errorData.detail || 'Unknown error'}`);
        }
        
        const result = await response.json();
        console.log('Echo Bot v2 response:', result);
        
        if (result.success && result.audio_url) {
            // Set the Murf-generated audio URL instead of raw recording
            playbackAudio.src = result.audio_url;
            playbackAudio.style.opacity = '1';
            
            // Show the transcription
            if (result.llm_response) {
                showTranscriptionResult(result.llm_response);
            } else if (result.transcript) {
                showTranscriptionResult(result.transcript);
            }

            // Auto-play the Murf-generated audio
            try {
                await playbackAudio.play();
                showUploadStatus('success', 'Echo Bot v2 Complete!', `Transcribed and generated speech with ${selectedVoice}`);
            } catch (playError) {
                console.log('Auto-play blocked, user can manually play');
                showUploadStatus('success', 'Echo Bot v2 Complete!', 'Click play to hear the AI-generated speech');
            }
            
        } else {
            throw new Error('No audio URL returned from Echo Bot v2');
        }
        
    } catch (error) {
        console.error('Echo Bot v2 error:', error);
        playbackAudio.style.opacity = '1';
        
        // Fallback to raw recording if Echo Bot v2 fails
        const playbackAudio = document.getElementById('playbackAudio');
        playbackAudio.src = audioURL;
        
        showUploadStatus('error', 'Echo Bot v2 Failed', 'Playing raw recording as fallback. ' + error.message);
    }
}

function showTranscriptionResult(transcript) {
    // Show transcription section
    const transcriptionSection = document.getElementById('transcriptionSection');
    const transcriptionText = document.getElementById('transcriptionText');
    
    if (transcriptionSection && transcriptionText) {
        transcriptionText.textContent = transcript;
        transcriptionText.style.fontStyle = 'normal';
        transcriptionText.style.color = 'rgba(255, 255, 255, 0.95)';
        transcriptionSection.style.display = 'block';
    }
}

async function uploadRecording() {
    if (!audioBlob) {
        showUploadStatus('error', 'Upload Failed', 'No recording available to upload');
        return;
    }

    try {
        const uploadBtn = document.getElementById('uploadButton');
        uploadBtn.disabled = true;
        
        showUploadStatus('uploading', 'Uploading...', 'Sending recording to server...');
        
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');
        
        const response = await fetch('/upload-audio', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            showUploadStatus('success', 'Upload Complete!', 
                `File: ${result.filename} (${formatFileSize(result.size)})`);
        } else {
            throw new Error('Upload response indicated failure');
        }
        
    } catch (error) {
        console.error('Upload error:', error);
        showUploadStatus('error', 'Upload Failed', error.message);
    } finally {
        const uploadBtn = document.getElementById('uploadButton');
        uploadBtn.disabled = false;
    }
}

async function transcribeRecording() {
    if (!audioBlob) {
        showUploadStatus('error', 'Transcription Failed', 'No recording available to transcribe');
        return;
    }

    try {
        const transcribeBtn = document.getElementById('transcribeButton');
        transcribeBtn.disabled = true;
        
        showUploadStatus('uploading', 'Transcribing...', 'Processing audio with AssemblyAI...');
        
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');
        
        const response = await fetch('/transcribe/file', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Transcription failed: ${response.status} ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (result.success && result.transcript) {
            showTranscriptionResult(result.transcript);
            showUploadStatus('success', 'Transcription Complete!', 'Audio transcribed successfully');
        } else {
            throw new Error('No transcription text received');
        }
        
    } catch (error) {
        console.error('Transcription error:', error);
        showUploadStatus('error', 'Transcription Failed', error.message);
    } finally {
        const transcribeBtn = document.getElementById('transcribeButton');
        transcribeBtn.disabled = false;
    }
}

function showUploadStatus(type, message, details) {
    const statusDiv = document.getElementById('uploadStatus');
    const statusIcon = statusDiv.querySelector('.status-icon');
    const statusMessage = statusDiv.querySelector('.status-message');
    const statusDetails = statusDiv.querySelector('.status-details');
    
    // Remove existing classes
    statusDiv.classList.remove('uploading', 'success', 'error');
    statusDiv.classList.add(type);
    
    statusMessage.textContent = message;
    statusDetails.textContent = details;
    
    statusDiv.style.display = 'block';
    
    // Auto-hide after 5 seconds for success/error
    if (type !== 'uploading') {
        setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 5000);
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}