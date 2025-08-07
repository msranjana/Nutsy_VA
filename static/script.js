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
        // Request microphone access
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                sampleRate: 44100
            } 
        });
        
        // Create MediaRecorder instance
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        // Reset audio chunks
        audioChunks = [];
        
        // Set up event handlers
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };
        
        mediaRecorder.onstop = () => {
            // Create blob from chunks
            audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            
            // Create URL and set up playback
            audioURL = URL.createObjectURL(audioBlob);
            const playbackAudio = document.getElementById('playbackAudio');
            playbackAudio.src = audioURL;
            
            // Show playback section
            document.getElementById('playbackSection').style.display = 'block';
            
            // Stop all tracks to release microphone
            stream.getTracks().forEach(track => track.stop());
        };
        
        // Start recording
        mediaRecorder.start(1000); // Collect data every second
        
        // Update UI
        updateRecordingUI(true);
        
        console.log('Recording started');
        
    } catch (error) {
        console.error('Error starting recording:', error);
        alert('Could not access microphone. Please ensure you have granted microphone permissions and try again.');
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        updateRecordingUI(false);
        console.log('Recording stopped');
    }
}

function updateRecordingUI(isRecording) {
    const startButton = document.getElementById('startRecording');
    const stopButton = document.getElementById('stopRecording');
    const recordingStatus = document.getElementById('recordingStatus');
    
    if (isRecording) {
        startButton.disabled = true;
        stopButton.disabled = false;
        recordingStatus.style.display = 'flex';
    } else {
        startButton.disabled = false;
        stopButton.disabled = true;
        recordingStatus.style.display = 'none';
    }
}

// Upload functionality
async function uploadRecording() {
    if (!audioBlob) {
        showUploadStatus('error', 'No recording available', 'Please record audio first');
        return;
    }

    const uploadBtn = document.getElementById('uploadButton');
    
    try {
        // Disable upload button and show uploading status
        uploadBtn.disabled = true;
        showUploadStatus('uploading', 'Uploading audio...', 'Please wait');

        // Create FormData and append the audio blob
        const formData = new FormData();
        // Use the original blob directly instead of creating a File object
        formData.append('file', audioBlob, 'recording.webm');

        // Send to server
        const response = await fetch('/upload-audio', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();
        
        // Show success message
        showUploadStatus('success', 'Upload successful!', `File: ${result.filename} (${formatFileSize(result.size)})`);
        
    } catch (error) {
        console.error('Upload error:', error);
        showUploadStatus('error', 'Upload failed', error.message);
    } finally {
        // Re-enable upload button after 2 seconds
        setTimeout(() => {
            uploadBtn.disabled = false;
        }, 2000);
    }
}

function showUploadStatus(type, message, details = '') {
    const uploadStatusDiv = document.getElementById('uploadStatus');
    const statusContent = uploadStatusDiv.querySelector('.status-content');
    
    // Remove existing status classes
    uploadStatusDiv.classList.remove('uploading', 'success', 'error');
    
    // Add new status class
    uploadStatusDiv.classList.add(type);
    
    // Update content
    statusContent.innerHTML = `
        <span class="status-icon"></span>
        <span class="status-message">${message}</span>
        ${details ? `<span class="status-details">${details}</span>` : ''}
    `;
    
    // Show the status
    uploadStatusDiv.style.display = 'block';
    
    // Hide after 5 seconds for success/error states
    if (type !== 'uploading') {
        setTimeout(() => {
            uploadStatusDiv.style.display = 'none';
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

// Simple test function for debugging
function testTranscribe() {
    console.log('🧪 Test transcribe function called!');
    alert('Transcribe button is working!');
}

// Transcription functionality
async function transcribeRecording() {
    console.log('🔍 Transcribe button clicked!');
    console.log('🔍 audioBlob exists:', !!audioBlob);
    
    if (!audioBlob) {
        console.log('❌ No audioBlob available');
        showUploadStatus('error', 'No recording available', 'Please record audio first');
        return;
    }

    console.log('✅ Starting transcription process...');
    const transcribeBtn = document.getElementById('transcribeButton');
    const transcriptionSection = document.getElementById('transcriptionSection');
    const transcriptionText = document.getElementById('transcriptionText');
    const transcriptionInfo = document.getElementById('transcriptionInfo');
    
    console.log('🔍 DOM elements found:', {
        transcribeBtn: !!transcribeBtn,
        transcriptionSection: !!transcriptionSection,
        transcriptionText: !!transcriptionText,
        transcriptionInfo: !!transcriptionInfo
    });
    
    try {
        // Disable transcribe button and show processing status
        transcribeBtn.disabled = true;
        transcribeBtn.textContent = '🔄 Transcribing...';
        
        // Show transcription section and clear previous content
        transcriptionSection.style.display = 'block';
        transcriptionText.textContent = 'Processing audio transcription...';
        transcriptionText.style.fontStyle = 'italic';
        transcriptionText.style.color = 'rgba(255, 255, 255, 0.7)';
        transcriptionInfo.innerHTML = '';

        console.log('📤 Sending request to /transcribe/file...');

        // Create FormData and append the audio blob
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');

        // Send to transcription endpoint
        const response = await fetch('/transcribe/file', {
            method: 'POST',
            body: formData
        });

        console.log('📥 Response received:', response.status, response.statusText);

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Transcription failed: ${response.status} - ${errorText}`);
        }

        const result = await response.json();
        
        // Display transcription results
        if (result.success && result.transcript) {
            transcriptionText.textContent = result.transcript;
            transcriptionText.style.fontStyle = 'normal';
            transcriptionText.style.color = 'rgba(255, 255, 255, 0.95)';
            
            // Update transcription info
            const infoItems = [];
            if (result.word_count) {
                infoItems.push(`<span class="info-item">📊 ${result.word_count} words</span>`);
            }
            if (result.audio_duration) {
                infoItems.push(`<span class="info-item">⏱️ ${result.audio_duration}s</span>`);
            }
            if (result.confidence) {
                infoItems.push(`<span class="info-item">✅ ${Math.round(result.confidence * 100)}% confidence</span>`);
            }
            
            transcriptionInfo.innerHTML = infoItems.join('');
            
            showUploadStatus('success', 'Transcription completed!', `${result.word_count} words transcribed`);
        } else {
            throw new Error('No transcription text received');
        }
        
    } catch (error) {
        console.error('Transcription error:', error);
        transcriptionText.textContent = 'Transcription failed. Please try again.';
        transcriptionText.style.fontStyle = 'italic';
        transcriptionText.style.color = '#f44336';
        transcriptionInfo.innerHTML = '';
        showUploadStatus('error', 'Transcription failed', error.message);
    } finally {
        // Re-enable transcribe button
        setTimeout(() => {
            transcribeBtn.disabled = false;
            transcribeBtn.textContent = '📝 Transcribe Audio';
        }, 2000);
    }
}
