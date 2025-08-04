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
