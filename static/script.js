// Meyme - Modern AI Voice Agent JavaScript
// Modified for real-time streaming and chat history display

// This function is now a self-contained module
(function() {

    function appendMessage(type, text) {
        const chatHistory = document.getElementById('chatHistory');
        if (!chatHistory) {
            console.error('Chat history element not found!');
            return;
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;

        if (type === 'user') {
            // Remove any previous interim message before adding the final user message
            const existingInterim = document.getElementById('interimMessage');
            if (existingInterim) {
                existingInterim.remove();
            }
            messageDiv.textContent = `You: ${text}`;
        } else if (type === 'interim') {
            // Check if an interim message already exists and update it
            let interimMessage = document.getElementById('interimMessage');
            if (interimMessage) {
                interimMessage.textContent = `(Listening...) ${text}`;
            } else {
                // If not, create a new one
                interimMessage = document.createElement('div');
                interimMessage.id = 'interimMessage';
                interimMessage.className = 'message interim-message';
                interimMessage.textContent = `(Listening...) ${text}`;
                chatHistory.appendChild(interimMessage);
            }
        }
        
        // Add final messages to the chat history
        if (type !== 'interim') {
            chatHistory.appendChild(messageDiv);
        }

        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    document.addEventListener('DOMContentLoaded', () => {
        const voiceButton = document.getElementById('voiceButton');
        const micIcon = document.getElementById('micIcon');
        const statusMessage = document.getElementById('statusMessage');

        let isRecording = false;
        let audioContext = null;
        let mediaStreamSource = null;
        let processor = null;
        let socket = null;

        const SAMPLE_RATE = 16000;
        const BUFFER_SIZE = 4096;

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

                processor = audioContext.createScriptProcessor(BUFFER_SIZE, 1, 1);

                processor.onaudioprocess = (e) => {
                    if (!isRecording || !socket || socket.readyState !== WebSocket.OPEN) {
                        return;
                    }

                    const inputData = e.inputBuffer.getChannelData(0);
                    const downsampledBuffer = downsampleBuffer(inputData, audioContext.sampleRate, SAMPLE_RATE);
                    const pcm16 = to16BitPCM(downsampledBuffer);
                    
                    socket.send(pcm16);
                };

                mediaStreamSource.connect(processor);
                processor.connect(audioContext.destination);

                socket = new WebSocket(`ws://${window.location.host}/ws`);

                socket.onopen = () => {
                    isRecording = true;
                    updateUIForRecording();
                    if (statusMessage) {
                        statusMessage.textContent = 'Listening...';
                    }
                };

                socket.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        console.log('Received message:', data);

                        if (data.type === 'turn_end') {
                            // Handle final transcripts
                            if (data.transcript && data.transcript.trim()) {
                                // Add to chat history
                                appendMessage('user', data.transcript);
                                
                                // Update status message with confidence
                                statusMessage.textContent = 
                                    `Turn complete: "${data.transcript}" (Confidence: ${(data.confidence * 100).toFixed(1)}%)`;
                                statusMessage.classList.add('turn-complete');
                                
                                setTimeout(() => {
                                    statusMessage.classList.remove('turn-complete');
                                    statusMessage.textContent = 'Listening...';
                                }, 3000);
                            } else {
                                statusMessage.textContent = 'Turn ended, listening...';
                            }
                        } else if (data.type === 'transcript' && !data.end_of_turn) {
                            // Handle interim transcripts
                            if (data.transcript) {
                                // Show interim transcript in status
                                statusMessage.textContent = `"${data.transcript}..." (speaking)`;
                                statusMessage.classList.add('speaking');
                                
                                // Show in chat as interim message
                                appendMessage('interim', data.transcript);
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
                if (statusMessage) {
                    statusMessage.textContent = 'Microphone access denied.';
                }
            }
        };

        const stopRecording = () => {
            if (isRecording) {
                isRecording = false;
                if (processor) {
                    processor.disconnect();
                }
                if (mediaStreamSource) {
                    mediaStreamSource.disconnect();
                }
                if (audioContext) {
                    audioContext.close();
                    audioContext = null;
                }
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.close();
                }
                updateUIForStopped();
                statusMessage.textContent = 'Press the mic button to start talking with the agent!';
            }
        };

        // Helper functions for audio processing
        function downsampleBuffer(buffer, originalSampleRate, newSampleRate) {
            // (Function body is unchanged)
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
            // (Function body is unchanged)
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
})();