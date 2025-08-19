// Meyme - Modern AI Voice Agent JavaScript
// Modified to send 16kHz, 16-bit, mono PCM audio via Web Audio API

document.addEventListener('DOMContentLoaded', () => {
    const voiceButton = document.getElementById('voiceButton');
    const micIcon = document.getElementById('micIcon');
    const statusMessage = document.getElementById('statusMessage');

    let isRecording = false;
    let audioContext = null;
    let mediaStreamSource = null;
    let processor = null;
    let socket = null;

    const SAMPLE_RATE = 16000; // AssemblyAI required sample rate
    const BUFFER_SIZE = 4096; // Audio processing buffer size

    const toggleRecording = async () => {
        if (isRecording) {
            stopRecording();
        } else {
            await startRecording();
        }
    };

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            mediaStreamSource = audioContext.createMediaStreamSource(stream);

            // Create a ScriptProcessorNode to process audio samples
            processor = audioContext.createScriptProcessor(BUFFER_SIZE, 1, 1);

            processor.onaudioprocess = (e) => {
                if (!isRecording || !socket || socket.readyState !== WebSocket.OPEN) {
                    return;
                }

                // Get the audio data from the input buffer (first channel for mono)
                const inputData = e.inputBuffer.getChannelData(0);

                // Resample and convert to 16-bit PCM
                const downsampledBuffer = downsampleBuffer(inputData, audioContext.sampleRate, SAMPLE_RATE);
                const pcm16 = to16BitPCM(downsampledBuffer);

                // Send the 16-bit PCM data over the WebSocket
                socket.send(pcm16);
            };

            mediaStreamSource.connect(processor);
            processor.connect(audioContext.destination);

            socket = new WebSocket(`ws://${window.location.host}/ws`);

            socket.onopen = () => {
                isRecording = true;
                updateUIForRecording();
                statusMessage.textContent = '🎙️ Listening...';
            };

            socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'turn_end') {
                        // This is the most important part of the streaming logic.
                        // The server detected a pause and sent the final transcript.
                        console.log('🔔 Turn Detection: End of turn detected!', data);
                        
                        // Display the final transcription at the end of the turn
                        if (data.transcript && data.transcript.trim()) {
                            statusMessage.textContent = `🎤 Turn complete: "${data.transcript}" (Confidence: ${(data.confidence * 100).toFixed(1)}%)`;
                            statusMessage.classList.add('turn-complete');
                            
                            // Remove the turn complete styling after 3 seconds
                            setTimeout(() => {
                                statusMessage.classList.remove('turn-complete');
                                statusMessage.textContent = '🎙️ Listening...';
                            }, 3000);
                        } else {
                            statusMessage.textContent = '🎙️ Turn ended, listening...';
                        }
                    } else if (data.type === 'transcript') {
                        // Handle regular transcript updates (for partial transcripts)
                        if (!data.end_of_turn && data.transcript) {
                            // Show partial transcripts in real-time but with different styling
                            statusMessage.textContent = `🎙️ "${data.transcript}..." (speaking)`;
                            statusMessage.classList.add('speaking');
                        } else if (data.end_of_turn && data.transcript) {
                            // This case is already handled by the 'turn_end' type, but good to have as a backup.
                            console.log('Transcript with end_of_turn:', data.transcript);
                        }
                    }
                } catch (e) {
                    console.error('Error parsing WebSocket message:', e);
                }
            };

            socket.onclose = () => {
                console.log('WebSocket connection closed');
                stopRecording();
            };

            socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                stopRecording();
            };

        } catch (error) {
            console.error('Error starting recording:', error);
            statusMessage.textContent = '❌ Microphone access denied. Please allow microphone permissions.';
        }
    };

    const stopRecording = () => {
        if (isRecording) {
            isRecording = false;
            // Clean up all Web Audio API resources
            if (processor) {
                processor.disconnect();
                processor = null;
            }
            if (mediaStreamSource) {
                mediaStreamSource.disconnect();
                mediaStreamSource = null;
            }
            if (audioContext) {
                audioContext.close();
                audioContext = null;
            }
            // Close the WebSocket connection
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.close();
            }
            updateUIForStopped();
            statusMessage.textContent = 'Press the mic button to start talking with Meyme!';
        }
    };

    // Helper functions for audio processing
    function downsampleBuffer(buffer, originalSampleRate, newSampleRate) {
        if (newSampleRate === originalSampleRate) {
            return buffer;
        }
        const ratio = originalSampleRate / newSampleRate;
        const newLength = Math.round(buffer.length / ratio);
        const result = new Float32Array(newLength);
        let offsetResult = 0;
        let offsetBuffer = 0;
        while (offsetResult < result.length) {
            const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
            let accum = 0;
            let count = 0;
            for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
                accum += buffer[i];
                count++;
            }
            result[offsetResult] = accum / count;
            offsetResult++;
            offsetBuffer = nextOffsetBuffer;
        }
        return result;
    }

    function to16BitPCM(input) {
        const dataLength = input.length * 2;
        const output = new Int16Array(dataLength / 2);
        for (let i = 0; i < input.length; i++) {
            let s = Math.max(-1, Math.min(1, input[i]));
            output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return output.buffer;
    }

    // UI update functions
    const updateUIForRecording = () => {
        voiceButton.classList.add('recording');
        micIcon.className = 'fas fa-stop';
    };

    const updateUIForStopped = () => {
        voiceButton.classList.remove('recording');
        micIcon.className = 'fas fa-microphone';
    };

    voiceButton.addEventListener('click', toggleRecording);
});