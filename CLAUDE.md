# Repository Guidelines

## How to Use This Guide

- Start here for project-wide guidance before changing Voice Bass.
- Use `README.md` for user-facing setup and usage instructions.
- Use `.claude/skills/*/SKILL.md` for detailed agent workflows.
- More specific skill instructions override this file when there is a conflict.

## Project Overview

Voice Bass is a TCC prototype for real-time AI voice transformation. The app captures microphone audio in an Electron frontend, sends PCM chunks through WebSocket to a Python backend, transcribes speech with Whisper, synthesizes speech with Edge-TTS, optionally applies RVC voice conversion, and optionally injects an AudioSeal watermark.

```text
Microphone -> Electron frontend -> WebSocket -> Python backend -> Speaker
                                             -> Whisper -> Edge-TTS -> RVC -> AudioSeal
```

## Components

| Component | Location | Purpose |
| --------- | -------- | ------- |
| Backend API | `backend/main.py` | FastAPI app, startup, HTTP config and WebSocket endpoint |
| Voice pipeline | `backend/pipeline.py` | STT, TTS, RVC, watermark and audio chunk processing |
| RVC engine | `backend/rvc_engine.py` | RVC model loading, inference and voice scanning |
| Frontend main | `frontend/main.js` | Electron main process and browser window setup |
| Preload bridge | `frontend/preload.js` | Safe bridge between Electron and renderer |
| Renderer | `frontend/renderer/app.js` | Microphone capture, WebSocket client and audio playback |
| UI/CSP | `frontend/renderer/index.html` | HTML shell and Content Security Policy |

## Available Skills

| Skill | Description |
| ----- | ----------- |
| `voice-bass-overview` | Project context, main files, risks and which skill to read first. |
| `backend-audio-pipeline` | Whisper, Edge-TTS, RVC, AudioSeal, temp files, thresholds and latency constraints. |
| `rvc-models` | How to add, scan, validate and handle RVC voice models in `backend/voices/`. |
| `websocket-contract` | Frontend/backend protocol, binary PCM chunks, JSON messages, endpoints and latency options. |
| `electron-audio-frontend` | Electron security, Web Audio capture/playback, CSP, devices and frontend latency UI. |
| `quality-architecture` | Clean code, clean architecture direction, tests, dependency discipline and refactor guidance. |

## Critical Rules

- Use Python 3.10.x for the backend. Do not upgrade to Python 3.14 for this project.
- Keep backend installation compatible with `rvc-python`: use `pip<24.1` and `setuptools<81` as described in `README.md`.
- FFmpeg must be available on PATH; audio changes must preserve compatibility with the system binary, not only Python packages.
- Preserve the audio contract unless changing frontend and backend together: PCM 16-bit mono chunks at 16 kHz are sent over WebSocket.
- Voice return latency must target a maximum of 1 second. Speech is segmented by VAD; the only user-facing time control is the pause-to-finalize (hangover): 300/400/500 ms, all at or below 1s. There is no user buffer anymore — do not reintroduce a buffer selector or add hangover options above 1s.
- Do not remove RVC, OmegaConf or Torch compatibility workarounds without validating existing `.pth` voice models.
- Keep AudioSeal optional: if it cannot load, the backend should continue without watermark and log the condition.
- Keep Electron renderer security enabled: `contextIsolation: true`, `nodeIntegration: false`, and Node access only through `preload.js`.
- Do not commit `.env`, generated audio, `venv`, `node_modules`, or large voice model files unless explicitly requested.

## Development Commands

### Backend

```powershell
cd backend
py -3.10 -m venv venv
venv\Scripts\activate.ps1
python -m pip install "pip<24.1" "setuptools<81" wheel
python -m pip install --no-build-isolation openai-whisper
python -m pip install -r requirements.txt
python main.py
```

### Frontend

```bash
cd frontend
npm install
npm start
```

Use `npm run dev` to open Electron with DevTools.

## Architecture Direction

- Keep the prototype simple, but move toward clear boundaries as the code grows.
- Prefer domain logic isolated from transport, UI, filesystem and third-party services.
- Avoid adding dependencies unless they are justified for Windows, Python 3.10, Electron and the ML/audio stack.
- Do not put new CPU/GPU-heavy work directly in async WebSocket handlers without considering an executor or worker boundary.
- Favor small, testable functions for audio format conversion, config parsing, voice scanning and protocol handling.

## Validation Expectations

There are no full automated quality gates yet. For now, changes should include the most relevant validation available:

- Backend starts with `python main.py`.
- Frontend starts with `npm start`.
- `/config` returns voices, pause (hangover) options (`hang_options`) and RVC models.
- `/ws/voice` accepts PCM chunks and returns transcription JSON plus WAV bytes.
- Audio changes are manually checked with a microphone and speaker.
- Latency-related changes verify that available options and expected voice return stay at or below 1 second.

## Commit and PR Guidelines

- Prefer concise conventional commit messages: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Keep documentation changes separate from behavioral refactors when possible.
- Document manual validation when tests are not available.
