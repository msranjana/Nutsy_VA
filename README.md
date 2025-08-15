# AI Voice AssistantA real-time voice chat interface that enables natural conversations with an AI assistant using speech recognition, language models, and text-to-speech synthesis.## 🌟 Features- **Voice Interaction**: Seamless speech-to-text and text-to-speech conversion- **Context Memory**: AI maintains conversation context for natural dialogue- **Real-time Processing**: Quick response times with streaming audio- **Error Handling**: Graceful fallbacks for various failure scenarios- **Modern UI**: Clean, responsive interface with visual feedback## 🛠️ Technology Stack### Frontend- HTML5 / CSS3 / JavaScript- MediaRecorder API for voice capture- Web Audio API for playback### Backend- FastAPI (Python web framework)- AssemblyAI for Speech-to-Text- Google's Gemini Pro for AI conversation- Murf.ai for Text-to-Speech- Python 3.9+## 🏗️ Architecture```Voice Input → Speech-to-Text → AI Processing → Text-to-Speech → Audio Output```1. **Voice Capture**: Browser's MediaRecorder API2. **Speech Recognition**: AssemblyAI API3. **Language Processing**: Gemini Pro API4. **Voice Synthesis**: Murf.ai API5. **State Management**: Server-side session handling## 🚀 Setup & Installation### Prerequisites- Python 3.9 or higher- Node.js (optional, for development)- API keys for:  - AssemblyAI  - Google Gemini  - Murf.ai### Environment Setup1. Clone the repository:```bashgit clone <repository-url>cd voice-agent```2. Create a virtual environment:```bashpython -m venv venv.\venv\Scripts\activate```3. Install dependencies:```bashpip install -r requirements.txt```4. Create `.env` file in the project root:```plaintextASSEMBLYAI_API_KEY=your_assemblyai_keyGEMINI_API_KEY=your_gemini_keyMURF_API_KEY=your_murf_key```### Running the Application1. Start the FastAPI server:```bashuvicorn main:app --reload --host 0.0.0.0 --port 8000```2. Open in browser:```http://localhost:8000```## 📝 API Documentation### Endpoints- `GET /`: Main application interface- `POST /agent/chat/{session_id}`: Voice chat endpoint- `GET /health`: API health check### Error HandlingThe application includes comprehensive error handling:- Speech recognition failures- AI processing errors- Audio synthesis issues- Network connectivity problems## 🔒 Security Considerations- API keys are stored in environment variables- User sessions are managed securely- Audio data is processed in-memory- CORS policies are implemented## 🧪 TestingRun the test suite:```bashpytest tests/```## 📦 DeploymentThe application can be deployed using:- Docker containers- Cloud platforms (AWS, GCP, Azure)- Traditional hosting with WSGI servers## 🤝 Contributing1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- AssemblyAI for speech recognition
- Google for the Gemini Pro API
- Murf.ai for voice synthesis
- FastAPI team for the amazing framework
