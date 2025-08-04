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
