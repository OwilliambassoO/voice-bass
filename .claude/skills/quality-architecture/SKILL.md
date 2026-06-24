---
name: quality-architecture
description: Guide clean code, clean architecture, testing, dependency choices and refactors in Voice Bass. Use when planning or implementing structural changes, new packages, tests, quality gates or cross-cutting improvements.
---

# Quality and Architecture

## Guiding Principles

- Keep current behavior understandable before refactoring.
- Prefer small, cohesive modules over large orchestration files as the project grows.
- Separate domain decisions from framework, filesystem, UI and third-party adapters.
- Add dependencies only when their value is clear for Windows, Python 3.10, Electron and the ML/audio stack.
- Do not hide fragile compatibility constraints behind unexplained abstractions.

## Architecture Direction

The project can evolve toward this shape without requiring a large rewrite:

```text
backend/
├── domain/        # audio contracts, voice model metadata, pipeline decisions
├── services/      # STT, TTS, RVC, watermark orchestration
├── adapters/      # Whisper, Edge-TTS, RVC, AudioSeal, filesystem
├── api/           # FastAPI routes and WebSocket handlers
└── tests/

frontend/
├── services/      # WebSocket client, config client
├── audio/         # capture, encoding, playback queue
├── ui/            # DOM rendering and events
└── security/      # preload-exposed contracts if needed
```

Use this as direction, not as a mandatory immediate migration.

## Latency as Architecture

- Voice return at or below 1 second is a product constraint.
- Treat latency above 1s as a design problem, not only a UI setting.
- Avoid changes that improve transcription quality by simply increasing the hangover/pause above 1s (there is no user buffer anymore; speech is segmented by VAD).
- Consider model size, queueing, blocking work, temp file I/O and playback buffering when evaluating latency.

## Backend Quality

- Extract pure helpers for audio conversion, threshold decisions and config mapping.
- Keep ML model loading separate from request handling where possible.
- Avoid global mutable state when introducing testable services.
- Prefer explicit errors and logs over broad silent fallbacks.
- Preserve the no-RVC and no-AudioSeal fallback paths.

## Frontend Quality

- Keep DOM updates separate from audio capture and WebSocket protocol code.
- Avoid spreading backend URLs and protocol constants across files.
- Keep Electron security defaults intact.
- Prefer explicit state transitions for disconnected, connecting, streaming and error states.

## Testing Direction

Start small:

- Backend tests for `/`, `/config` and pure audio helpers.
- Tests or smoke scripts that mock heavy ML dependencies.
- Frontend linting before large UI refactors.
- Manual validation notes for microphone, speaker, RVC and latency.

## Dependency Rules

- Do not update core ML/audio dependencies casually.
- For Python, document why a package is needed and whether it works on Python 3.10.
- For Node, avoid adding build tooling unless the project is ready to own it.
- Prefer standard library or existing packages when they solve the need clearly.

## Review Checklist

- Does the change preserve the WebSocket/audio contract?
- Does it keep voice return within 1 second?
- Does it avoid weakening Electron security?
- Does it keep setup compatible with the README?
- Is the code easier to test or reason about after the change?
- Is manual or automated validation documented?
