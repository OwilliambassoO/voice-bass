---
name: backend-audio-pipeline
description: Work on the Voice Bass backend audio pipeline with Whisper, Edge-TTS, RVC and AudioSeal. Use when changing backend audio processing, thresholds, temp files, latency, model loading or pipeline behavior.
---

# Backend Audio Pipeline

## Read Before Editing

- `backend/services/voice_pipeline.py` — orchestration: `transcribe_pcm` and `synthesize_text`.
- `backend/services/streaming_session.py` — per-connection VAD: accumulating buffer, silence/hangover, partial/final events.
- `backend/adapters/` (`whisper_adapter`, `edge_tts_adapter`, `rvc_adapter`, `audioseal_adapter`) for library specifics.
- `backend/domain/thresholds.py` for RMS and confidence thresholds.
- `backend/api/voice_websocket.py` and `backend/api/config_routes.py` if the change affects the protocol or `/config`.
- `README.md` for setup constraints and troubleshooting.

## Pipeline Contract

The backend receives small PCM 16-bit mono chunks (~250 ms) at 16 kHz and returns
transcription messages plus, at the end of each utterance, processed WAV bytes. Speech is
segmented by **VAD** (Voice Activity Detection): a per-connection `StreamingSession`
accumulates the current utterance instead of transcribing isolated chunks (isolated chunks
made Whisper lose context and hallucinate).

Current flow:

1. Per ~30 ms frame, classify speech vs silence using the RMS threshold.
2. While speech grows, re-transcribe the accumulated buffer ~1×/s and emit a **partial** transcription (live text).
3. Finalize on a continuous silence (hangover: 300/400/500 ms, default 500) or a 15 s utterance cap.
4. On finalize: transcribe the full buffer (Whisper, Portuguese), reject no-speech or low-confidence output, then synthesize **once** for the whole phrase: Edge-TTS, then RVC if a model is loaded, then AudioSeal if available.
5. Return the **final** transcription message followed by the WAV bytes.

## Latency Rule

- There is no user buffer anymore; the only time control is the pause-to-finalize
  (hangover), 300/400/500 ms.
- Keep the 1s ceiling as a responsiveness target for partial transcription and per-stage
  latency, not as a hard cap on the total response of a long phrase (which depends on the
  phrase length plus the hangover).
- If a change increases per-stage STT, TTS, RVC or AudioSeal latency in a way that breaks
  real-time responsiveness, flag it as a functional regression.

## Compatibility Rules

- Use Python 3.10.x.
- Do not upgrade `pip`, `setuptools`, Torch, `omegaconf` or `rvc-python` casually.
- Keep the `OmegaConf.resolve` compatibility behavior unless AudioSeal and RVC have both been validated.
- Keep AudioSeal optional: failure to load should warn and continue without watermark.
- Keep FFmpeg available on PATH as an environment requirement.

## Async and Performance

- The heavy stages (Whisper, RVC, AudioSeal) run via `asyncio.to_thread` in
  `voice_pipeline`; Edge-TTS is natively async.
- The WebSocket uses an **unbounded ordered queue** drained by a single worker, so
  reception is decoupled from processing. Do NOT add chunk-dropping/backpressure: dropping
  audio corrupts the accumulated utterance and reintroduces the hallucinations VAD fixed.
- `transcribe_pcm` and `synthesize_text` are separate, so STT runs ~1×/s for partials while
  synthesis runs only once per utterance. Keep that split.
- Prefer small pure helpers in `domain/` for format conversion, thresholds and validation so they can be tested without loading ML models.

## Temp Files

- Register every temp file for cleanup.
- Be careful on Windows: open file handles can block deletion.
- Prefer in-memory processing only when the involved libraries support it reliably.

## Validation

At minimum, validate:

- Backend starts with `python main.py`.
- Silence does not trigger synthesis (no utterance is finalized).
- A spoken phrase produces a live partial transcription, then a final transcription plus WAV after the pause.
- RVC bypass works when no model is loaded.
- AudioSeal failure does not crash the pipeline.
- Pause (hangover) options are 300 / 400 / 500 ms; partial transcription stays responsive.
