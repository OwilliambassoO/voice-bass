---
name: websocket-contract
description: Maintain the Voice Bass frontend/backend WebSocket contract. Use when changing /ws/voice, /config, binary audio chunks, JSON messages (config/transcription partial-final), hangover/pause options, sample rate or protocol behavior.
---

# WebSocket Contract

## Read Before Editing

Backend:

- `backend/api/voice_websocket.py` — `/ws/voice`: receives chunks, handles `config`/`ping`, emits transcription (partial/final) + WAV.
- `backend/api/config_routes.py` — `GET /config` (voices, `hang_options`, rvc_models).
- `backend/services/streaming_session.py` — accumulating-buffer transcription, silence/hangover, partial/final events.
- `backend/services/voice_pipeline.py` — `transcribe_pcm` (STT) and `synthesize_text` (TTS→RVC→AudioSeal).

Frontend:

- `frontend/renderer/app.js` — assembles the `config` message and wires WS callbacks.
- `frontend/renderer/services/websocket-client.js` — send/receive, parses the `partial` flag.
- `frontend/renderer/services/config.js` — URLs, `SAMPLE_RATE`, `CHUNK_SAMPLES`.
- `frontend/renderer/ui/controls.js` — hangover radio (`hangMsValue`).
- `frontend/renderer/index.html` — CSP and the "Pausa para finalizar" radios.

## Protocol Overview

```text
Renderer -> Backend: binary PCM16 audio chunks (~250ms each)
Renderer -> Backend: JSON text messages for config/control
Backend -> Renderer: JSON transcription messages (partial=true while speaking,
                     partial=false at end of utterance)
Backend -> Renderer: binary WAV output (one per utterance, after the final text)
```

The backend does NOT transcribe each chunk independently. It accumulates the
current utterance and re-transcribes the growing buffer (Whisper needs context;
isolated 1s windows hallucinate). On a short silence it finalizes: synthesizes
the voice once and resets. See the `backend-audio-pipeline` skill for internals.

## Current Endpoints

- HTTP config: `GET /config`
- WebSocket voice stream: `WebSocket /ws/voice`
- Default backend origin: `http://localhost:8000` and `ws://localhost:8000`

If a URL changes, update both:

- The `BACKEND_*` constants in `frontend/renderer/services/config.js`.
- CSP `connect-src` in `frontend/renderer/index.html`.

## `GET /config` response

```json
{
  "voices": [{ "id": "pt-BR-AntonioNeural", "label": "..." }],
  "hang_options": [{ "ms": 300, "label": "..." }, { "ms": 400 }, { "ms": 500 }],
  "rvc_models": [{ "id": "<folder>", "label": "<folder>" }]
}
```

`hang_options` replaced the old `buffer_options`. The frontend currently
hard-codes the matching radios in `index.html`; keep both lists in sync.

## Messages

Renderer -> Backend (text JSON):

- `{ "action": "config", "voice": str, "rvc_model": str|null, "hang_ms": int }`
  - `hang_ms`: silence (ms) that ends an utterance; applied live to the session.
  - Response: `{ "type": "config_ack", "voice", "rvc_model", "hang_ms" }`.
- `{ "action": "ping" }` -> `{ "type": "pong" }`.

Renderer -> Backend (binary): PCM16 mono 16 kHz chunk.

Backend -> Renderer:

- `{ "type": "transcription", "text": str, "partial": true }` — live partial;
  the UI updates one line in place (`controls.js` `addTranscription`).
- `{ "type": "transcription", "text": str, "partial": false }` — final text;
  immediately followed by the WAV bytes for that utterance.
- `{ "type": "error", "message": str }`.

Only non-empty `text` is sent. Empty/non-speech chunks produce no message.

## Audio Contract

- Sample rate: 16 kHz. Channels: mono. Input: PCM16. Output: WAV bytes.
- Chunk size is fixed at `CHUNK_SAMPLES` (~250 ms): small so the silence/hangover
  detection reacts quickly. The backend is chunk-size agnostic.

Change format only by updating frontend capture, backend decoding and docs together.

## Pause (hangover) and latency

- "Real-time" here = live partial **text** (~1x/s). Audio is synthesized once per
  utterance, so audio return ≈ utterance length + processing — by design (the
  user accepted this; do not revert to per-chunk audio, which is choppy).
- The user-facing control is the **pause-to-finalize (hangover)**: 300/400/500 ms,
  all ≤ 1s. Smaller = more responsive; larger = avoids cutting at natural pauses.
- Partial-transcription cadence (`_PARTIAL_MIN_GROWTH_S`) is decoupled from chunk
  size so smaller chunks do not multiply STT cost.
- Do not add large buffers as a workaround for recognition quality.

## JSON Message Rules

- Keep payloads small and explicit; handle malformed JSON safely on both sides.
- When adding a new action/message, document sender, payload fields, expected
  response and error behavior here.

## Validation

After protocol changes:

- Backend starts and `/config` returns `voices`, `hang_options`, `rvc_models`.
- Frontend connects to `/ws/voice`; binary PCM chunks are accepted.
- Live partial transcriptions update one line; the final message is followed by WAV.
- Changing the pause radio updates the session (see backend log "Hangover ... ajustado").
- `cd backend && venv\Scripts\python.exe -m pytest tests -q` passes.
