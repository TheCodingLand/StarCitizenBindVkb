# xAI Voice Agent — Realtime API Guide

You are helping a developer integrate the xAI Realtime Voice API into their application. This is a public API — the developer is working outside of xAI and accessing the API via their own API key from [console.x.ai](https://console.x.ai). The session configuration below reflects settings they configured in the xAI console playground.

**Official documentation:** https://docs.x.ai/developers/model-capabilities/audio/voice-agent — always refer to this for the latest API details, supported models, pricing, and parameters.

**Key rules:**
- Ask the discovery questions first, in a single message.
- Do not write code until the developer answers.
- After receiving answers, generate a tailored implementation and skip sections that do not apply.
- Never expose the raw XAI API key in browser/client code.

---

## 0. Discovery Questions (ask before any code)

Ask all of the following:

1. **Language / platform** — Which would you like to build with? (e.g. Node.js, Python, Browser)
2. **API key** — Do you already have an xAI API key with the Voice endpoint enabled, or do you need to create one? (Keys are created at [console.x.ai](https://console.x.ai) → API Keys.)
3. **Existing project** — Are you integrating this into an existing app (e.g. a web app, Electron, React Native, mobile WebView, telephony server), or starting a new project from scratch?
4. **Audio I/O** — How will audio be captured and played back? (e.g. system microphone + speakers, telephony/SIP trunk, pre-recorded files, browser MediaStream)
5. **Framework** — Are you using a specific framework? (e.g. React, Next.js, Vue, Svelte, Express, FastAPI, Flask, Django) This helps tailor the code to your stack.
6. **UI components** — For the frontend, would you like to use [shadcn/ui](https://ui.shadcn.com/) to scaffold a polished UI quickly, or do you prefer building with your own custom components?
7. **LiveKit** — Would you like to use [LiveKit](https://livekit.io/) as a transport layer? LiveKit handles audio capture, playback, echo cancellation, and interruption for you — but adds infrastructure (LiveKit Cloud or self-hosted server + a separate agent process). **Recommended when:**
   - You need **multi-user rooms** (group calls with an AI participant)
   - You need **phone/SIP integration** (AI agent answering phone calls)
   - You need **production-grade echo cancellation** (WebRTC AEC is significantly better than `getUserMedia` constraints)
   - You want to **swap AI providers** without changing client code
   - You're **already using LiveKit** for video/audio features

   **Not recommended when** you're building a simple 1:1 browser voice agent — the direct WebSocket approach has fewer moving parts, lower latency (no middleman), and deploys as a single app.

Once you have answers, use the API spec and implementation notes below to generate a tailored implementation. Skip sections that don't apply to the developer's setup. If the developer chose LiveKit, see section 9.

---

## 1. Auth

**API key** — starts with `xai-`. Set as env var:

```bash
export XAI_API_KEY="xai-..."
```

If they need a new key: [console.x.ai](https://console.x.ai) → API Keys → create key → enable **Voice** endpoint.

**Server-side** (Node.js, Python): pass as a Bearer token in the `Authorization` header.

**Browser / client-side**: never expose the API key. Mint a short-lived session token from a backend:

```bash
curl -X POST https://api.x.ai/v1/realtime/client_secrets \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"expires_after": {"seconds": 300}}'
```

Response: `{"value": "token-...", "expires_at": 1234567890}`

Then connect using the token as a WebSocket subprotocol: `xai-client-secret.<token>`

**Important:** Session tokens expire. Implement auto-refresh — schedule a new fetch ~5 seconds before `expires_at`. Use exponential backoff on retry failures (`min(1000 * 2^attempt, 10000)` ms, max 5 retries).

## 2. Connection

WebSocket endpoint: `wss://api.x.ai/v1/realtime`

**Note:** The Voice Agent API is only available in the `us-east-1` region.

**Server-side (Node.js):**
```javascript
import WebSocket from 'ws';
const ws = new WebSocket('wss://api.x.ai/v1/realtime', {
  headers: { Authorization: `Bearer ${process.env.XAI_API_KEY}` },
});
```

**Server-side (Python):**
```python
import websockets
async with websockets.connect(
    "wss://api.x.ai/v1/realtime",
    additional_headers={"Authorization": f"Bearer {API_KEY}"}
) as ws:
```

**Browser (with ephemeral token):**
```javascript
const ws = new WebSocket('wss://api.x.ai/v1/realtime', [
  `xai-client-secret.${sessionToken}`
]);
```

## 3. Session Configuration

Send as the first message after the connection opens:

```json
{
  "type": "session.update",
  "session": {
    "voice": "Eve",
    "instructions": "",
    "turn_detection": {
      "type": "server_vad"
    },
    "tools": [
      {
        "type": "web_search"
      },
      {
        "type": "x_search"
      }
    ],
    "input_audio_transcription": {
      "model": "grok-2-audio"
    },
    "audio": {
      "input": {
        "format": {
          "type": "audio/pcm",
          "rate": 24000
        }
      },
      "output": {
        "format": {
          "type": "audio/pcm",
          "rate": 24000
        }
      }
    }
  }
}
```

**`input_audio_transcription` is required** if you want user speech transcripts (`conversation.item.input_audio_transcription.completed` events). Without it, you'll get audio responses but never see what the user said in text.

Available voices: `Eve`, `Ara`, `Leo`, `Rex`, `Sal`.

Available audio formats:
| Format | Description | Sample Rate |
|--------|-------------|-------------|
| `audio/pcm` | Raw 16-bit PCM, little-endian | 8000, 16000, 22050, 24000 (default), 32000, 44100, 48000 |
| `audio/pcmu` | G.711 μ-law (telephony, North America/Japan) | Fixed 8000 |
| `audio/pcma` | G.711 A-law (telephony, Europe/international) | Fixed 8000 |

### Additional tool types

The session config above includes the tools configured in the playground. The API also supports:

**Collections (RAG) — `file_search`:** search uploaded documents via the [Collections API](https://docs.x.ai/developers/rest-api-reference/collections):
```json
{ "type": "file_search", "vector_store_ids": ["your-collection-id"], "max_num_results": 10 }
```

**Custom function tools:** define your own tools with JSON schemas for booking, lookups, etc.:
```json
{
  "type": "function",
  "name": "get_weather",
  "description": "Get current weather for a location",
  "parameters": {
    "type": "object",
    "properties": { "location": { "type": "string", "description": "City name" } },
    "required": ["location"]
  }
}
```


## 4. Audio Protocol

**Sending audio** (mic → API): capture 16-bit PCM at 24 kHz, base64-encode each chunk, and send:

```json
{"type": "input_audio_buffer.append", "audio": "<base64>"}
```

With `server_vad`: the API auto-detects speech end and triggers a response.
Without VAD (`turn_detection: null`): manually send `input_audio_buffer.commit` then `response.create`.

**Receiving audio** (API → speaker): audio arrives as base64 PCM chunks in `response.output_audio.delta` events at 24 kHz. Decode and enqueue for playback.

**Interruption** — must be handled automatically in your event handler:
1. Listen for `input_audio_buffer.speech_started`
2. Immediately stop audio playback / clear the playback buffer
3. Send `{"type": "response.cancel"}`

**Sending text** (instead of audio):

```json
{"type": "conversation.item.create", "item": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Hello!"}]}}
{"type": "response.create"}
```

**Custom function call flow** (when using `function` tools):
1. Receive `response.function_call_arguments.done` with `name`, `call_id`, `arguments`
2. Execute the function locally
3. Send result: `{"type": "conversation.item.create", "item": {"type": "function_call_output", "call_id": "<call_id>", "output": "<JSON string>"}}`
4. Send `{"type": "response.create"}` to let the agent continue

## 5. Event Reference

### Server → client

| Event | Description |
|---|---|
| `session.created` | Session ready — `event.session.id`, `event.session.model` |
| `session.updated` | Session config acknowledged |
| `conversation.created` | Conversation session created (first message) |
| `conversation.item.added` | User or assistant message added to history — `event.item` |
| `input_audio_buffer.speech_started` | VAD detected user speaking — **interrupt playback and cancel response** |
| `input_audio_buffer.speech_stopped` | VAD detected user stopped speaking |
| `input_audio_buffer.committed` | Audio buffer committed |
| `conversation.item.input_audio_transcription.completed` | User speech transcribed — `event.transcript` |
| `response.created` | New assistant response started — `event.response.id` |
| `response.output_item.added` | New output item (message or function_call) — `event.item` |
| `response.output_item.done` | Output item finished — `event.item.status` |
| `response.output_audio.delta` | Audio chunk — `base64.decode(event.delta)` |
| `response.output_audio.done` | Audio stream finished for this turn |
| `response.output_audio_transcript.delta` | Streamed transcript text — `event.delta` |
| `response.output_audio_transcript.done` | Transcript complete — `event.transcript` |
| `response.function_call.created` | Tool call started — `event.name`, `event.call_id` |
| `response.function_call_arguments.done` | Function args complete — `event.name`, `event.call_id`, `event.arguments` |
| `response.function_call.done` | Function call processing complete |
| `response.content_part.added` | Content part started |
| `response.content_part.done` | Content part finished |
| `response.done` | Response complete — `event.usage` has `input_tokens`, `output_tokens`, `total_tokens` |
| `rate_limits.updated` | Rate limit status — `event.rate_limits[]` |
| `error` | Error — `event.code`, `event.message` |

### Client → server

| Event | Description |
|---|---|
| `session.update` | Update session config |
| `input_audio_buffer.append` | Send audio chunk — `{ audio: "<base64>" }` |
| `input_audio_buffer.commit` | Commit buffer (manual turn detection only) |
| `input_audio_buffer.clear` | Clear uncommitted audio |
| `conversation.item.create` | Send text/audio message or function call output |
| `conversation.item.delete` | Delete an item from history |
| `response.create` | Trigger assistant response |
| `response.cancel` | Cancel in-progress response |

## 6. Implementation Notes (Direct WebSocket — Browser)

These are hard-won architectural decisions from a working production implementation. Follow them exactly.

### ⚠️ AudioWorklet processor file (REQUIRED)

You MUST create a static file that the AudioWorklet can load. Place it in `public/pcm-processor-worklet.js`:

```javascript
// public/pcm-processor-worklet.js
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0]?.[0];
    if (input) {
      const int16 = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(int16, [int16.buffer]);
    }
    return true;
  }
}
registerProcessor('pcm-processor', PCMProcessor);
```

Then register it in your mic capture code:
```javascript
const audioContext = new AudioContext({ sampleRate: 24000 });
await audioContext.audioWorklet.addModule('/pcm-processor-worklet.js');
const source = audioContext.createMediaStreamSource(stream);
const workletNode = new AudioWorkletNode(audioContext, 'pcm-processor');
workletNode.port.onmessage = (event) => {
  const int16Data = event.data; // Int16Array — base64-encode and send
};
source.connect(workletNode);
```

**Do NOT use `ScriptProcessorNode` / `createScriptProcessor`** — it is deprecated, runs on the main thread, and causes audio glitches.

### ⚠️ AudioContext warmup (REQUIRED for Safari)

Safari enforces a strict autoplay policy: an AudioContext must be created or resumed from a **direct** user-gesture handler (click / tap). Call this from the button click that starts the session, **before** any async work like WebSocket connect:

```javascript
// Inside the "Connect" button handler, BEFORE await connect():
const audioCtx = new AudioContext({ sampleRate: 24000 });
if (audioCtx.state === 'suspended') await audioCtx.resume();
```

If you create the AudioContext later (inside a WebSocket callback or after an `await`), Safari will permanently suspend it and audio will never play.

### ⚠️ Parallel initialization (REQUIRED)

Start microphone capture and the WebSocket connection **simultaneously** — do NOT wait for the WebSocket `open` event before capturing audio. Even with fast networks, the WebSocket handshake + authentication takes 100–800 ms. Starting mic capture only after connection adds noticeable delay.

```javascript
// Inside the "Connect" button handler — both start at the same time:

// 1. Start mic capture immediately
const stream = await navigator.mediaDevices.getUserMedia({
  audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, sampleRate: 24000 },
});
const audioCtx = new AudioContext({ sampleRate: 24000 });
if (audioCtx.state === 'suspended') await audioCtx.resume(); // Safari warmup

await audioCtx.audioWorklet.addModule('/pcm-processor-worklet.js');
const source = audioCtx.createMediaStreamSource(stream);
const workletNode = new AudioWorkletNode(audioCtx, 'pcm-processor');
source.connect(workletNode);

// 2. Buffer audio until WebSocket + session are ready
let micBuffer = [];       // Array of Int16Array chunks
let isSessionReady = false;

workletNode.port.onmessage = (event) => {
  const int16Data = event.data;
  if (isSessionReady) {
    // Live streaming — send directly
    ws.send(JSON.stringify({
      type: 'input_audio_buffer.append',
      audio: audioToBase64(int16Data),
    }));
  } else {
    // Buffer until session is ready
    micBuffer.push(int16Data);
  }
};

// 3. Connect WebSocket in parallel (don't block on mic setup above)
const ws = new WebSocket('wss://api.x.ai/v1/realtime', [
  \`xai-client-secret.\${sessionToken}\`
]);

ws.onopen = () => {
  ws.send(JSON.stringify({ type: 'session.update', session: { /* ... */ } }));
};

// 4. Wait for session.updated before sending any audio
ws.onmessage = ({ data }) => {
  const event = JSON.parse(data);
  if (event.type === 'session.updated' && !isSessionReady) {
    isSessionReady = true;
    // Flush buffered audio in order
    for (const chunk of micBuffer) {
      ws.send(JSON.stringify({
        type: 'input_audio_buffer.append',
        audio: audioToBase64(chunk),
      }));
    }
    micBuffer = [];
  }
  // ... handle other events
};
```

### ⚠️ Mic buffering before session ready (CRITICAL)

Users begin speaking within 100–300 ms of tapping the mic button. Without buffering, the first 200–700 ms of their utterance is **permanently lost**, making the agent feel unresponsive from the very first interaction. This is the single most impactful best practice for perceived quality.

**Rules:**
1. Start pushing every mic chunk into a buffer array the moment audio capture begins.
2. Do NOT send any audio to the server until **both** the WebSocket is open AND `session.updated` has been received.
3. Once both conditions are met, flush the entire buffer in chronological order via `input_audio_buffer.append` messages.
4. After flushing, switch to normal real-time streaming for new chunks.

**Production tips:**
- Use a safety cap (~10 seconds / ~240,000 samples at 24 kHz) to prevent memory issues.
- Flush in reasonably sized messages (~400–800 samples each) for smooth transmission.
- On reconnection, immediately resume buffering new audio while the new session initializes.

### Browser audio playback

Schedule `AudioBufferSourceNode`s on the `AudioContext` timeline for gapless playback. Track a `nextPlayTime` variable:

```javascript
let nextPlayTime = 0;
const queuedSources = [];

function playPcmChunk(base64) {
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  const int16 = new Int16Array(bytes.buffer);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768;

  const buf = audioCtx.createBuffer(1, float32.length, 24000);
  buf.getChannelData(0).set(float32);
  const src = audioCtx.createBufferSource();
  src.buffer = buf;
  src.connect(audioCtx.destination);

  const now = audioCtx.currentTime;
  const startAt = Math.max(now, nextPlayTime);
  src.start(startAt);
  nextPlayTime = startAt + buf.duration;
  queuedSources.push(src);
  src.onended = () => {
    const idx = queuedSources.indexOf(src);
    if (idx !== -1) queuedSources.splice(idx, 1);
  };
}
```

To interrupt, stop all queued sources and reset the timeline:
```javascript
function interruptPlayback() {
  for (const src of queuedSources) { try { src.stop(); } catch {} }
  queuedSources.length = 0;
  nextPlayTime = 0;
}
```

### ⚠️ Base64 encoding — avoid stack overflow

Do NOT use `btoa(String.fromCharCode(...new Uint8Array(buffer)))` — the spread operator crashes on large audio buffers. Use chunked encoding:

```javascript
function audioToBase64(int16Array) {
  const bytes = new Uint8Array(int16Array.buffer, int16Array.byteOffset, int16Array.byteLength);
  const CHUNK = 0x2000; // 8 KiB chunks
  const parts = [];
  for (let i = 0; i < bytes.length; i += CHUNK) {
    parts.push(String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK)));
  }
  return btoa(parts.join(''));
}
```

### Microphone setup
Always request with `{ echoCancellation: true, noiseSuppression: true, autoGainControl: true, sampleRate: 24000 }`. Handle errors:
- `NotAllowedError` → "Microphone access denied — check browser permissions"
- `NotFoundError` → "No microphone found"
- Listen for `track.ended` events to detect mic disconnection mid-session

### Next.js token minting
Use a **Server Action** (preferred) or an API route at `/api/token` to mint session tokens server-side. The `XAI_API_KEY` stays in `process.env` and is never sent to the browser.

### Transcript streaming
Track the current assistant response by ID (use a `ref` or state). When `response.output_audio_transcript.delta` arrives, append `event.delta` to the message with that response's ID. When `response.done` fires, clear the current response ref. This prevents interleaved user transcription events from corrupting the assistant's message.

### Interruption UX
When `input_audio_buffer.speech_started` fires — this must happen **automatically** in your event handler:
1. Call `interruptPlayback()` to stop all queued audio
2. Send `response.cancel` to the WebSocket
3. Mark the current assistant message as interrupted (e.g. `opacity-50`)
4. Clear the current response tracking ref

### Connection lifecycle
- Use a connection timeout (10 seconds). If the WebSocket doesn't reach `OPEN`, resolve as failed.
- Track intentional disconnects to suppress error callbacks when the user clicks "Disconnect".
- On unmount: stop mic tracks, close AudioContext, disconnect WebSocket.
- After disconnect, refetch the session token for the next connection.
- **On reconnection**: keep the mic stream alive and immediately resume buffering new audio into the mic buffer. When the new WebSocket opens and `session.updated` arrives, flush the buffer — this preserves any speech the user uttered during the reconnection window.

## 6. Implementation Notes (Node.js / Python — Server-side)

### Node.js
- Use the `ws` npm package for WebSocket
- Use `node-record-lpcm16` + `sox` for mic capture (macOS: `brew install sox`)
- Use `speaker` npm package for audio playback at 24000 Hz
- Audio format: raw PCM, 16-bit signed integer, mono channel
- Destroy and recreate the `Speaker` instance on interruption

### Python
- Use `websockets` (`pip install websockets`)
- Use `pyaudio` for mic capture and playback (`pip install pyaudio`, requires PortAudio: `brew install portaudio`)
- Run mic capture as an `asyncio.Task` alongside the WebSocket receive loop
- Use PyAudio callback mode for playback to avoid blocking the event loop
- Graceful shutdown: catch `SIGINT`, cancel tasks, close streams, terminate PyAudio

## 7. shadcn/ui (if selected)

Skip this section if the developer prefers custom UI.

```bash
npx shadcn@latest init
npx shadcn@latest add button card badge scroll-area avatar input select slider switch tooltip separator dialog label textarea
```

### Page layout

The app should fill the viewport — **do not** wrap it in a narrow card. Use a full-height, full-width layout:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Header (sticky top)                                                │
│  ┌──────────────────────────────────────┬─────────────────────────┐  │
│  │  Title + Badge (connection status)   │  ⚙️ Settings   Connect  │  │
│  └──────────────────────────────────────┴─────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Transcript area (flex-1, overflow-y-auto, ScrollArea)               │
│  max-w-3xl mx-auto, py-6                                            │
│                                                                      │
│    ┌─ user message ──────────────────────────────────────────┐       │
│    │  Avatar   "What's the weather in SF?"                   │       │
│    └─────────────────────────────────────────────────────────┘       │
│    ┌─ assistant message ─────────────────────────────────────┐       │
│    │  Avatar   "Let me check... It's 62°F and sunny in SF." │       │
│    └─────────────────────────────────────────────────────────┘       │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Footer (sticky bottom, border-t)                                    │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  max-w-3xl mx-auto                                          │    │
│  │  [  Text input ...                          ] [Send] [🎙️]  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Sheet/Dialog (Settings — opens from ⚙️)                             │
│  ├─ Voice: Select (Eve/Ara/Leo/Rex/Sal)                              │
│  ├─ Instructions: Textarea                                           │
│  ├─ VAD Threshold: Slider (0.1–0.9, step 0.05)                       │
│  ├─ Silence Duration: Slider (0–10000ms)                             │
│  ├─ Prefix Padding: Slider (0–10000ms)                               │
│  └─ Enable Search: Switch                                            │
└──────────────────────────────────────────────────────────────────────┘
```

### Styling rules

- **Container**: `h-dvh flex flex-col` on the outermost `<div>` — the app fills the viewport, no scrollbar on `<body>`. Do **not** use a `Card` as the outermost wrapper; the page itself is the chrome.
- **Header**: `sticky top-0 z-10 border-b bg-background/80 backdrop-blur px-4 py-3 flex items-center justify-between`. Title on the left, controls on the right.
- **Transcript area**: `flex-1 overflow-y-auto` with content constrained to `max-w-3xl mx-auto px-4 py-6`. Messages should breathe — use `gap-4` between them. This is the only scrollable region.
- **Messages**: full-width rows with `flex gap-3 items-start`. Avatar on the left (both user and assistant). Text in a `<div>` (not a bubble with a background — keep it clean). User text in `text-foreground`, assistant text in `text-muted-foreground` or a slightly different shade. Interrupted messages get `opacity-50`.
- **Footer**: `sticky bottom-0 border-t bg-background px-4 py-3`. Input row constrained to `max-w-3xl mx-auto`. Use a large `Input` with rounded-full styling and icon buttons inside or beside it.
- **Mic button**: prominent, round, changes color when active (e.g. `bg-destructive` while recording with a pulse animation).
- **Theme**: dark mode by default (`dark` class on `<html>`). Background `bg-background` (zinc-950 / neutral-950). Minimal borders, generous spacing.
- **Responsive**: the layout naturally fills any width. The `max-w-3xl` on the content area keeps readability on ultrawide screens while looking great on tablets and phones. No breakpoints needed for the core layout.

### Audio visualizer (optional but recommended)

Add a simple waveform or orb animation that responds to audio levels. This gives immediate visual feedback that the mic is working and the assistant is speaking. A pulsing circle that scales with RMS amplitude is the simplest effective approach — use CSS `scale` transitions on a rounded `<div>`.

### Key patterns

1. **State management** — `useReducer` or Zustand for: `connectionStatus`, `messages[]`, `settings`, `error`.
2. **Audio hook** — `useVoiceAgent()` custom hook: WebSocket lifecycle, AudioWorklet capture, AudioContext playback. Returns `{ connect, disconnect, status, messages, sendText }`.
3. **Auto-scroll** — `useEffect` + `ref.scrollIntoView({ behavior: 'smooth' })` on the transcript area when `messages` changes.
4. **Status badge** — `idle` → secondary, `connecting` → outline + spinner, `active` → green dot, `error` → destructive.
5. **Settings** — `Sheet` (slides from right) is better than `Dialog` for settings panels. Warn if session is active — changes require reconnecting.

## 8. Voice Agent UX Guidelines

These UX principles are non-negotiable. Follow them when building the voice agent UI.

### "Can I speak right now?"

This is the only question the user should ever need to answer, and the UI must answer it instantly at all times.

### Two visible states, not four

Internally there are four states (idle, connecting, active, error). The user sees two: **off** and **listening**. Connecting looks identical to active — the mic button flips to its listening appearance the moment it's tapped. If connection fails, it snaps back to off with an error message. The user never waits in an ambiguous middle state.

### The mic button is the only control

One button starts the session. The same area shows how to stop it. No separate connect/disconnect in the header, no modal flows. Tap to talk, tap stop to end.

### Continuous mic feedback

The user needs proof their microphone is working before they start speaking. A visual element tied to real-time mic input level (RMS amplitude) provides this. When the user is silent it's still; when they speak it responds. This replaces the need for a "test your mic" step.

### Interruption is automatic

When the user speaks over the assistant, playback stops immediately and the in-progress response is canceled. No button press, no "hold to talk." The assistant yields the moment it detects speech. The interrupted message stays in the transcript but is visually dimmed so the user understands it was cut short.

### Text input is secondary

Text input only appears when a voice session is active. Voice is the primary modality — text is a fallback for sending something you don't want to say out loud. It's hidden when idle to keep focus on the mic.

### Errors are recoverable with the same gesture

Any failure (mic denied, timeout, disconnect) resets to idle with a plain-language message. The user retries by tapping the mic again. No separate retry button, no reload required.

### Settings never interrupt a session

Settings are accessible any time but changes apply on the next connection. If a session is active, warn that changes won't take effect until they stop and restart.

## 9. LiveKit Integration (if selected)

Skip this section unless the developer chose LiveKit in question 7.

### Architecture

```
Browser ──WebRTC──► LiveKit Server ──WebSocket──► xAI Realtime API
  (SDK)              (Cloud/self)     (Agent)
```

The browser never connects to xAI directly. LiveKit handles all audio transport, echo cancellation, and interruption. You build two things: a **LiveKit Agent** (server-side, connects to xAI) and a **client** (uses LiveKit's React SDK).

### Prerequisites

```bash
# Agent (Python)
pip install livekit-agents livekit-plugins-openai

# Client (React)
npm install @livekit/components-react livekit-client livekit-server-sdk
```

You need either a [LiveKit Cloud](https://cloud.livekit.io/) account or a self-hosted LiveKit server.

### Agent (Python)

xAI's Realtime API is protocol-compatible with OpenAI's, so LiveKit's `openai-realtime` plugin works by overriding `base_url`:

```python
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.plugins import openai
import os

async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    model = openai.realtime.RealtimeModel(
        base_url="wss://api.x.ai/v1/realtime",
        api_key=os.environ["XAI_API_KEY"],
        voice="Eve",
        turn_detection=openai.realtime.ServerVadOptions(),
    )
    agent = openai.realtime.RealtimeAgent(model=model)
    agent.start(ctx.room)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

Run with: `python agent.py dev`

### Client (React)

The client only needs to connect to LiveKit — no audio handling code at all:

```tsx
"use client";
import { LiveKitRoom, RoomAudioRenderer, BarVisualizer, useVoiceAssistant } from "@livekit/components-react";

function VoiceAgent({ token, serverUrl }: { token: string; serverUrl: string }) {
  return (
    <LiveKitRoom token={token} serverUrl={serverUrl} connect={true}>
      <RoomAudioRenderer />
      <AgentUI />
    </LiveKitRoom>
  );
}

function AgentUI() {
  const { state, audioTrack } = useVoiceAssistant();
  return (
    <div>
      <p>Status: {state}</p>
      <BarVisualizer trackRef={audioTrack} />
    </div>
  );
}
```

### Token endpoint (Next.js)

```typescript
// app/api/livekit-token/route.ts
import { AccessToken } from "livekit-server-sdk";
import { NextResponse } from "next/server";

export async function POST() {
  const token = new AccessToken(
    process.env.LIVEKIT_API_KEY!,
    process.env.LIVEKIT_API_SECRET!,
    { identity: `user-${crypto.randomUUID()}` },
  );
  token.addGrant({ roomJoin: true, room: "voice-agent" });
  return NextResponse.json({ token: await token.toJwt() });
}
```

### What LiveKit handles for you
- Audio capture, encoding, and transport (WebRTC)
- Echo cancellation, noise suppression, automatic gain control
- Audio playback and interruption
- Reconnection and network resilience
- Multi-participant support

### What you still manage
- LiveKit Cloud account or self-hosted server
- The Python agent process (separate from your Next.js app)
- Two sets of credentials: `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` + `XAI_API_KEY`

## 10. Other Integrations

- **Pipecat** — Open-source Python framework for voice agents with native xAI support: [Docs](https://docs.pipecat.ai/server/services/s2s/grok) | [Example](https://github.com/pipecat-ai/pipecat/blob/main/examples/foundational/51-grok-realtime.py)
- **Voximplant** — Enterprise telephony with SIP support: [Docs](https://voximplant.com/products/grok-client) | [GitHub](https://github.com/voximplant/grok-voice-agent-example)

## 11. Checklist — verify before shipping

- [ ] **Mic capture starts in parallel with WebSocket connect** — not sequentially after connection opens
- [ ] **Audio is buffered until `session.updated`** — no audio sent before the server acknowledges the session config; buffer is flushed in order once ready
- [ ] **Buffer has a safety cap** (~10 seconds) to prevent memory issues on slow connections
- [ ] **PCM worklet file exists** in `public/` and is loadable at the correct path
- [ ] **AudioContext created inside user gesture** (click handler), not in a callback or after an await
- [ ] **Base64 encoding uses chunked approach** (not spread operator — crashes on large buffers)
- [ ] **`input_audio_transcription`** is set in session config (otherwise no user transcripts)
- [ ] **`speech_started` handler** interrupts playback AND sends `response.cancel` automatically
- [ ] **Token refresh** is implemented with auto-refetch before expiry
- [ ] **Cleanup on unmount**: mic tracks stopped, AudioContext closed, WebSocket disconnected
- [ ] **Mic permissions** requested with `echoCancellation`, `noiseSuppression`, `autoGainControl`
- [ ] **Error handling**: connection timeout, mic denied, mic disconnected, WebSocket errors
- [ ] **No API key in browser code** — only ephemeral tokens via subprotocol
- [ ] **Reconnection resumes buffering** — mic stays active and buffers audio during reconnect