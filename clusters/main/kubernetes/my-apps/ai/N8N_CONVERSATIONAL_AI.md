# n8n Conversational AI Integration Guide

This guide covers n8n nodes and workflows for building conversational AI assistants that integrate with Whisper (speech-to-text), SearXNG (search), and Ollama (local LLM).

## Built-in n8n AI Nodes

### 1. **AI Agent Node** (Recommended for Conversational AI)
- **Location**: Built-in → LangChain → Agent
- **Use Case**: Create autonomous conversational agents that can make decisions and use tools
- **Features**:
  - Maintains conversation context
  - Can integrate with external tools (SearXNG, HTTP APIs)
  - Supports multiple LLM backends (OpenAI, Ollama, etc.)
- **Documentation**: https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/

### 2. **OpenAI Node**
- **Location**: Built-in → OpenAI
- **Use Case**: Direct integration with OpenAI's GPT models
- **Features**:
  - Text completion
  - Chat conversations
  - Function calling
- **Note**: For local/private use, use Ollama instead

### 3. **AI Transform Node**
- **Location**: Built-in → Core Nodes → AI Transform
- **Use Case**: Generate code snippets and transform data using AI
- **Features**:
  - Context-aware code generation
  - Understands workflow structure

### 4. **Chat UI Integration**
- **Location**: Built-in → Chat Trigger
- **Use Case**: Web-based chat interface with voice input support
- **Features**:
  - Voice input (sends audio to webhook)
  - Text input
  - Real-time responses
- **Documentation**: https://n8nchatui.com/docs/configuration/voice-input

## Community Nodes for Conversational AI

### 1. **Ollama Node** (Community)
- **Package**: `@n8n/n8n-nodes-ollama` or similar
- **Use Case**: Integrate with your local Ollama instance
- **Access**: Your Ollama is at `ollama.${DOMAIN_0}` or `ollama-api.${DOMAIN_0}`
- **Installation**: 
  1. Go to Settings → Community Nodes
  2. Search for "ollama"
  3. Install the node package

### 2. **Whisper Integration** (HTTP Request Node)
- **Use Case**: Speech-to-text transcription
- **Method**: Use HTTP Request node to call Whisper API
- **Endpoint**: `http://whisper-app-template.ai.svc.cluster.local:9000/asr`
- **Configuration**:
  ```json
  {
    "method": "POST",
    "url": "http://whisper-app-template.ai.svc.cluster.local:9000/asr",
    "body": {
      "file": "{{ $binary.data }}",
      "task": "transcribe",
      "language": "en",
      "response_format": "json"
    },
    "bodyContentType": "form-data"
  }
  ```

## Recommended Workflow Structure

### Voice Command Workflow

```
1. Chat Trigger (Webhook)
   ↓ (receives audio file or text)
   
2. IF Node (Check if audio or text)
   ├─→ [Audio] HTTP Request → Whisper API
   │   ↓ (transcribe audio)
   │   Function Node (extract text: {{ $json.text }})
   └─→ [Text] Pass through
   ↓
   
3. AI Agent Node (or Ollama Node)
   - Model: Your Ollama model (e.g., llama3, mistral)
   - System Prompt: "You are a helpful home assistant..."
   - Tools: SearXNG search tool
   ↓
   
4. SearXNG Tool (if search needed)
   - URL: https://searxng.${DOMAIN_0}/search
   - Query: {{ $json.query }}
   ↓
   
5. Format Response
   ↓
   
6. Return to Chat UI
```

### Example: Complete Voice Assistant Workflow

```javascript
// 1. Webhook receives audio
const audioData = $input.item.json.binary?.data;

// 2. If audio, transcribe with Whisper
if (audioData) {
  // HTTP Request to Whisper
  const transcription = await whisperAPI.transcribe(audioData);
  return transcription.text;
}

// 3. Process with AI Agent
const response = await aiAgent.process({
  message: transcription || $input.item.json.message,
  tools: [searxngSearchTool],
  context: $workflow.context
});

// 4. Return response
return {
  text: response.text,
  audio: null // Optionally convert to speech
};
```

## Integration with Your Services

### Ollama Integration
- **Internal URL**: `http://ollama-app-template.ai.svc.cluster.local:11434`
- **API Endpoint**: `/api/generate` or `/api/chat`
- **Models Available**: Check via `GET /api/tags`
- **Example Request**:
  ```json
  {
    "model": "llama3",
    "prompt": "{{ $json.message }}",
    "stream": false
  }
  ```

### SearXNG Integration
- **Internal URL**: `https://searxng.${DOMAIN_0}`
- **API Endpoint**: `/search`
- **Parameters**:
  - `q`: Search query
  - `format`: `json`
- **Example**:
  ```
  GET https://searxng.${DOMAIN_0}/search?q={{ $json.query }}&format=json
  ```

### Whisper Integration
- **Internal URL**: `http://whisper-app-template.ai.svc.cluster.local:9000`
- **Health Check**: `GET /health`
- **Transcribe**: `POST /asr` (multipart/form-data)

## Advanced: Multi-Agent System

For complex workflows, you can create multiple specialized agents:

1. **Voice Input Agent**: Handles audio transcription
2. **Intent Recognition Agent**: Determines user intent
3. **Search Agent**: Performs SearXNG searches
4. **Response Agent**: Generates natural language responses
5. **Action Agent**: Executes commands (if needed)

## Text-to-Speech (Optional)

For voice responses, consider:
- **ElevenLabs Node** (community): High-quality TTS
- **Google TTS Node** (community): Free tier available
- **HTTP Request**: Use a TTS API service

## Best Practices

1. **Error Handling**: Always wrap API calls in try-catch
2. **Rate Limiting**: Implement delays between requests
3. **Context Management**: Use workflow context to maintain conversation history
4. **Security**: Keep sensitive data in n8n credentials
5. **Testing**: Test each node individually before chaining

## Example Workflow Templates

### Simple Q&A Workflow
```
Chat Trigger → AI Agent (Ollama) → Response
```

### Search-Enabled Assistant
```
Chat Trigger → AI Agent → SearXNG Tool → Format → Response
```

### Voice-Enabled Assistant
```
Chat Trigger → Whisper (if audio) → AI Agent → SearXNG (if needed) → Response
```

## Resources

- [n8n AI Integrations](https://n8n.io/integrations/categories/ai/)
- [n8n Chat UI Documentation](https://n8nchatui.com/)
- [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [SearXNG API Documentation](https://docs.searxng.org/dev/search_api.html)

## Next Steps

1. Install community nodes (Ollama, if available)
2. Create a test workflow with Chat Trigger
3. Add Whisper integration for voice input
4. Connect to Ollama for local LLM
5. Add SearXNG for search capabilities
6. Test and refine your conversational AI assistant

