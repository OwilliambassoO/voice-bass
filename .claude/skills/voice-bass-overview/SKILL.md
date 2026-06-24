---
name: voice-bass-overview
description: Understand Voice Bass project context, architecture, main files and risks. Use before broad changes, onboarding, planning, architecture review or when the user asks how the project works.
---

# Voice Bass Overview

## Purpose

Voice Bass is a TCC prototype for real-time voice transformation. It combines speech-to-text, text-to-speech, RVC voice conversion and watermarking to support privacy, inclusion and entertainment use cases.

## Current Flow

```text
Microphone -> Electron renderer -> WebSocket -> FastAPI backend
            <- WAV playback     <- Pipeline  <- Whisper -> Edge-TTS -> RVC -> AudioSeal
```

## Read First

- `README.md`: user-facing setup, architecture, pause (hangover) options and troubleshooting.
- `backend/main.py`: FastAPI startup (`lifespan`), dependency injection, `/config` and `/ws/voice`.
- The backend is layered (Clean Architecture): `domain/` (pure rules, `thresholds`),
  `adapters/` (Whisper, Edge-TTS, RVC, AudioSeal wrappers), `services/`
  (`voice_pipeline` orchestration plus `streaming_session` VAD), `api/` (routes/protocol).
- `backend/adapters/rvc_adapter.py` and `adapters/voice_scanner.py`: RVC loading and `backend/voices/` scanning.
- `frontend/renderer/app.js`: composes the modular renderer (`audio/`, `services/`, `ui/`) for capture, WebSocket and playback.

## Core Constraints

- Backend uses Python 3.10.x.
- Backend dependency installation is fragile because of `rvc-python`, `fairseq`, `omegaconf`, Torch and Whisper.
- Audio sent to the backend is PCM 16-bit mono at 16 kHz.
- Voice return must target at most 1 second. Options above 1s should be removed or avoided.
- Electron security must keep `contextIsolation: true` and `nodeIntegration: false`.

## Skill Selection

- Changing audio processing: read `backend-audio-pipeline`.
- Changing endpoints, payloads, WebSocket messages or latency options: read `websocket-contract`.
- Adding or debugging voice models: read `rvc-models`.
- Changing the renderer, capture, playback, devices or CSP: read `electron-audio-frontend`.
- Planning refactors, tests or dependency changes: read `quality-architecture`.

## Risk Areas

- Event loop blocking from CPU/GPU-heavy work.
- Silent dependency drift in `requirements.txt`.
- Large or unsafe `.pth` model files.
- Frontend/backend protocol mismatch.
- Latency regressions above 1 second.
- Security regressions in Electron or CORS/WebSocket exposure.
