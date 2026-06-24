---
name: electron-audio-frontend
description: Work on the Voice Bass Electron frontend, Web Audio capture, playback, device selection, CSP and renderer security. Use when editing frontend/main.js, preload.js, renderer HTML, CSS or app.js.
---

# Electron Audio Frontend

## Read Before Editing

- `frontend/main.js` and `frontend/backend-manager.js` (the main process also orchestrates the embedded backend).
- `frontend/preload.js`
- `frontend/renderer/index.html`
- `frontend/renderer/app.js` composes the modular renderer; the actual logic lives in
  `renderer/audio/` (`capture.js`, `worklet-processor.js`, `playback-queue.js`),
  `renderer/services/` (`websocket-client.js`, `config-client.js`) and `renderer/ui/`
  (`controls.js`, `status.js`, `visualizer.js`).
- `websocket-contract` skill if network, protocol or pause/hangover changes.

## Security Rules

- Keep `contextIsolation: true`.
- Keep `nodeIntegration: false`.
- Do not expose broad Node APIs to the renderer.
- Add new native capabilities through `preload.js` with a small, named API.
- Avoid Electron `remote`.

## CSP and Backend URLs

The renderer uses CSP in `frontend/renderer/index.html`.

When changing backend host, port or protocol, update both:

- Connection/fetch code in `frontend/renderer/app.js`.
- `connect-src` in the CSP meta tag.

## Web Audio Rules

- Preserve 16 kHz mono PCM16 chunks unless backend changes are coordinated.
- Capture already migrated from `ScriptProcessorNode` to an `AudioWorklet`
  (`renderer/audio/worklet-processor.js`), which accumulates samples and converts to Int16
  off the main thread. Do not revert to `ScriptProcessorNode`.
- Capture chunks are fixed at ~250 ms; their job is to detect the silence/pause with low
  latency, not to bound the transcription. Do not make them user-configurable.
- Avoid accidental microphone loopback into speakers unless explicitly intended.
- Keep output device handling defensive because `setSinkId` support can vary.

## Pause (Hangover) UI Rule

- The user-facing time control is the **pause-to-finalize (hangover)**, not a capture
  buffer. Options are 300 / 400 / 500 ms (`hang_options` from `/config`), all ≤ 1s.
- There is no buffer selector anymore; do not reintroduce one. Speech is segmented by VAD
  (accumulating buffer finalized on silence). See the `websocket-contract` skill.
- Smaller hangover = more responsive but may cut at natural pauses; larger = avoids cuts.
- Keep the 1s ceiling as a responsiveness target for partial transcription and per-stage
  latency; the total response of a long phrase depends on its length plus the hangover.

## WebSocket Robustness

- Guard JSON parsing.
- Keep binary and text message paths separate.
- Avoid unbounded playback queues.
- Prefer explicit reconnect behavior with clear user status.

## Validation

After frontend changes:

- `npm start` opens Electron.
- Microphone permission and device selection work.
- Backend connection status updates correctly.
- Audio chunks reach the backend.
- WAV playback works on the selected output device.
- Partial transcription updates live while speaking; final audio returns after the pause.
- Pause (hangover) options are 300 / 400 / 500 ms, all at or below 1 second.
