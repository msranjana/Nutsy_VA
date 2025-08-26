document.addEventListener('DOMContentLoaded', () => {
  const voiceButton = document.getElementById('voiceButton');
  const micIcon = document.getElementById('micIcon');
  const statusMessage = document.getElementById('statusMessage');
  let isRecording = false;
  let audioContext = null;
  let mediaStreamSource = null;
  let processor = null;
  let socket = null;
  let accumulatedAudioChunks = [];
  let playbackAudioContext = null;
  let isPlayingAudio = false;
  let currentAudioSource = null;
  let playbackStartTime = 0;
  let totalPlaybackDuration = 0;
  const SAMPLE_RATE = 16000;
  const BUFFER_SIZE = 4096;
  const PLAYBACK_SAMPLE_RATE = 44100;

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
        if (!isRecording || !socket || socket.readyState !== WebSocket.OPEN) return;
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
        statusMessage.textContent = '🎙️ Nutsy is listening...';  // Changed
        statusMessage.classList.add('show');
        if (isPlayingAudio) stopAudioPlayback();
        accumulatedAudioChunks = [];
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'audio_chunk') {
            accumulatedAudioChunks.push(data.base64_audio);
            playAudioChunk(data.base64_audio, data.chunk_index);
            statusMessage.textContent = `🎵 Nutsy is speaking...`;  // Changed
            statusMessage.classList.remove('turn-complete', 'processing', 'speaking', 'partial');
            statusMessage.classList.add('speaking');
            return;
          }

          if (data.type === 'audio_complete') {
            (async () => {
              try {
                statusMessage.textContent = '🎵 Nutsy is speaking...';  // Changed
                statusMessage.classList.remove('processing', 'turn-complete', 'partial');
                statusMessage.classList.add('speaking');
                if (accumulatedAudioChunks.length > 0) {
                  await assembleAndPlayCompleteAudio(accumulatedAudioChunks);
                } else {
                  statusMessage.textContent = '❌ No audio received';
                }
              } catch (error) {
                statusMessage.textContent = '❌ Audio playback failed';
              }
            })();
            if (socket && socket.readyState === WebSocket.OPEN) {
              socket.close();
            }
            return;
          }

          if (data.type === 'transcript' && data.transcript) {
            if (data.is_partial) {
              statusMessage.textContent = data.transcript;
              statusMessage.classList.remove('turn-complete', 'processing');
              statusMessage.classList.add('speaking', 'partial');
            } else if (data.end_of_turn) {
              statusMessage.textContent = data.transcript;
              statusMessage.classList.remove('speaking', 'partial');
              statusMessage.classList.add('turn-complete');
              setTimeout(() => {
                statusMessage.textContent = '🤖 Meyme is thinking...';
                statusMessage.classList.remove('turn-complete');
                statusMessage.classList.add('processing');
              }, 1000);
            } else {
              statusMessage.textContent = data.transcript;
              statusMessage.classList.remove('turn-complete', 'processing', 'partial');
              statusMessage.classList.add('speaking');
            }
          }
        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
        }
      };

      socket.onclose = () => {
        stopRecording();
      };

      socket.onerror = (error) => {
        stopRecording();
      };

    } catch (error) {
      statusMessage.textContent = '❌ Microphone access denied. Please allow microphone permissions.';
    }
  };

  const stopRecording = () => {
    if (isRecording) {
      isRecording = false;
      if (socket && socket.readyState === WebSocket.OPEN) {
        try {
          socket.send(JSON.stringify({
            type: 'end_turn',
            message: 'User finished speaking'
          }));
        } catch (error) {}
        setTimeout(() => {
          if (socket && socket.readyState === WebSocket.OPEN) socket.close();
        }, 30000);
      }
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
      updateUIForStopped();
      statusMessage.textContent = '🤖 Nutsy is thinking...';  // Changed
      statusMessage.classList.remove('speaking', 'partial', 'turn-complete');
      statusMessage.classList.add('processing');
    }
  };

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

  const updateUIForRecording = () => {
    voiceButton.classList.add('recording');
    micIcon.className = 'fas fa-stop';
  };

  const updateUIForStopped = () => {
    voiceButton.classList.remove('recording');
    micIcon.className = 'fas fa-microphone';
  };

  async function initPlaybackAudioContext() {
    if (!playbackAudioContext) {
      try {
        playbackAudioContext = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate: PLAYBACK_SAMPLE_RATE
        });
        if (playbackAudioContext.state === 'suspended') {
          await playbackAudioContext.resume();
        }
      } catch (error) {
        throw error;
      }
    }
    return playbackAudioContext;
  }

  async function base64ToAudioBuffer(base64Audio, chunkIndex) {
    try {
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const context = await initPlaybackAudioContext();
      const wavHeader = binaryString.substring(0, 12);
      const isValidWav = wavHeader.startsWith('RIFF') && wavHeader.includes('WAVE');
      if (!isValidWav && chunkIndex > 1) {
        throw new Error(`Chunk #${chunkIndex} is not a valid WAV file`);
      }
      return await context.decodeAudioData(bytes.buffer);
    } catch (error) {
      throw error;
    }
  }

  async function playAudioChunk(base64Audio, chunkIndex) {
    try {
      const audioBuffer = await base64ToAudioBuffer(base64Audio, chunkIndex);
      const context = await initPlaybackAudioContext();
      const source = context.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(context.destination);
      let startTime = context.currentTime;
      if (isPlayingAudio) {
        startTime = Math.max(context.currentTime, playbackStartTime + totalPlaybackDuration);
      } else {
        isPlayingAudio = true;
        playbackStartTime = context.currentTime;
        totalPlaybackDuration = 0;
      }
      totalPlaybackDuration += audioBuffer.duration;
      source.start(startTime);
      source.onended = () => {
        if (context.currentTime >= playbackStartTime + totalPlaybackDuration - 0.1) {
          isPlayingAudio = false;
          playbackStartTime = 0;
          totalPlaybackDuration = 0;
          setTimeout(() => {
            statusMessage.textContent = '🎙️ Press the mic button to speak to Nutsy!';  // Changed
            statusMessage.classList.remove('speaking', 'processing');
          }, 500);
        }
      };
      currentAudioSource = source;
    } catch (error) {}
  }

  function stopAudioPlayback() {
    if (currentAudioSource) {
      try { currentAudioSource.stop(); } catch { }
      currentAudioSource = null;
    }
    isPlayingAudio = false;
    playbackStartTime = 0;
    totalPlaybackDuration = 0;
  }

  async function assembleAndPlayCompleteAudio(audioChunks) {
    try {
      if (isPlayingAudio) stopAudioPlayback();
      await playCombinedWavChunks(audioChunks);
    } catch (error) {
      statusMessage.textContent = '❌ Audio assembly failed - trying fallback...';
      try {
        if (audioChunks.length > 0) {
          const fallbackBuffer = await base64ToAudioBuffer(audioChunks, 'EMERGENCY_FALLBACK');
          await playAssembledAudio(fallbackBuffer);
        }
      } catch {
        statusMessage.textContent = '❌ Audio playback failed completely';
        isPlayingAudio = false;
        currentAudioSource = null;
        setTimeout(() => {
          statusMessage.textContent = '🎬 Press the mic button to try again';
        }, 3000);
      }
    }
  }

  async function playCombinedWavChunks(base64Chunks) {
    try {
      const pcmData = [];
      const SAMPLE_RATE = 44100;
      const NUM_CHANNELS = 1;
      const BIT_DEPTH = 16;
      for (let i = 0; i < base64Chunks.length; i++) {
        const bytes = base64ToUint8Array(base64Chunks[i]);
        if (i === 0) {
          const wavHeader = String.fromCharCode(...bytes.slice(0, 12));
          if (wavHeader.startsWith('RIFF') && wavHeader.includes('WAVE')) {
            pcmData.push(bytes.slice(44));
          } else {
            pcmData.push(bytes);
          }
        } else {
          pcmData.push(bytes);
        }
      }
      const totalPcmLength = pcmData.reduce((sum, chunk) => sum + chunk.length, 0);
      const combinedPcm = new Uint8Array(totalPcmLength);
      let offset = 0;
      for (const chunk of pcmData) {
        combinedPcm.set(chunk, offset); offset += chunk.length;
      }
      const wavHeader = createWavHeader(combinedPcm.length, SAMPLE_RATE, NUM_CHANNELS, BIT_DEPTH);
      const finalWav = new Uint8Array(wavHeader.length + combinedPcm.length);
      finalWav.set(wavHeader, 0);
      finalWav.set(combinedPcm, wavHeader.length);
      const blob = new Blob([finalWav], { type: 'audio/wav' });
      const audioUrl = URL.createObjectURL(blob);
      const audioPlayer = document.getElementById('audioPlayer');
      if (!audioPlayer) throw new Error('Audio player element not found');
      audioPlayer.src = audioUrl;
      audioPlayer.style.display = 'none';
      statusMessage.textContent = `🎵 Nutsy is speaking...`;  // Changed
      statusMessage.classList.remove('processing', 'turn-complete', 'partial');
      statusMessage.classList.add('speaking');

      const onLoadedData = () => {
        isPlayingAudio = true;
        audioPlayer.play().catch(() => {
          statusMessage.textContent = '🎵 Click the audio player for full response';
        });
      };
      const onEnded = () => {
        isPlayingAudio = false;
        URL.revokeObjectURL(audioUrl);
        audioPlayer.removeEventListener('loadeddata', onLoadedData);
        audioPlayer.removeEventListener('ended', onEnded);
        audioPlayer.removeEventListener('error', onError);
        setTimeout(() => {
          statusMessage.textContent = '🎙️ Press the mic button to speak to Nutsy!';  // Changed
          statusMessage.classList.remove('speaking', 'processing');
          accumulatedAudioChunks = [];
        }, 500);
      };
      const onError = () => {
        statusMessage.textContent = '❌ Audio playback failed';
        statusMessage.classList.remove('speaking', 'processing');
        isPlayingAudio = false;
        audioPlayer.classList.remove('show');
        URL.revokeObjectURL(audioUrl);
        audioPlayer.removeEventListener('loadeddata', onLoadedData);
        audioPlayer.removeEventListener('ended', onEnded);
        audioPlayer.removeEventListener('error', onError);
      };

      audioPlayer.addEventListener('loadeddata', onLoadedData);
      audioPlayer.addEventListener('ended', onEnded);
      audioPlayer.addEventListener('error', onError);
    } catch (error) {
      throw error;
    }
  }

  async function playAssembledAudio(audioBuffer) {
    try {
      const context = await initPlaybackAudioContext();
      const source = context.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(context.destination);
      isPlayingAudio = true;
      playbackStartTime = context.currentTime;
      totalPlaybackDuration = audioBuffer.duration;
      currentAudioSource = source;
      statusMessage.textContent = `🎵 Nutsy is speaking...`;  // Changed
      source.start(0);
      source.onended = () => {
        isPlayingAudio = false;
        playbackStartTime = 0;
        totalPlaybackDuration = 0;
        currentAudioSource = null;
        setTimeout(() => {
          accumulatedAudioChunks = [];
          statusMessage.textContent = '🎙️ Press the mic button to speak to Nutsy!';  // Changed
          statusMessage.classList.remove('speaking', 'processing');
        }, 500);
      };
    } catch (error) {
      throw error;
    }
  }

  function base64ToUint8Array(base64) {
    const binary = atob(base64);
    const len = binary.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  function createWavHeader(dataLength, sampleRate = 44100, numChannels = 1, bitDepth = 16) {
    const blockAlign = (numChannels * bitDepth) / 8;
    const byteRate = sampleRate * blockAlign;
    const buffer = new ArrayBuffer(44);
    const view = new DataView(buffer);
    function writeStr(offset, str) {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
      }
    }
    writeStr(0, 'RIFF');
    view.setUint32(4, 36 + dataLength, true);
    writeStr(8, 'WAVE');
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitDepth, true);
    writeStr(36, 'data');
    view.setUint32(40, dataLength, true);
    return new Uint8Array(buffer);
  }

  voiceButton.addEventListener('click', toggleRecording);
});
