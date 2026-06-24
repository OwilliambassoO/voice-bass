---
name: rvc-models
description: Add, validate, scan and troubleshoot RVC voice models for Voice Bass. Use when working with backend/voices, .pth or .index files, model loading, voice selection or RVC inference.
---

# RVC Models

## Read Before Editing

- `README.md` section "Adicionando uma Voz RVC".
- `backend/adapters/rvc_adapter.py` and `backend/adapters/voice_scanner.py`.
- `backend/services/voice_pipeline.py` if model selection or inference behavior changes.
- `frontend/renderer/ui/controls.js` if voice selection in the UI changes.

## Directory Contract

Each voice model lives in its own folder under `backend/voices/`:

```text
backend/voices/
└── VoiceName/
    ├── VoiceName.pth
    └── added_IVF512_Flat.index
```

Rules:

- Exactly one `.pth` file per voice folder is expected.
- `.index` is optional but recommended for better fidelity.
- If multiple `.pth` or `.index` files exist, current scanning may choose the first sorted file; do not rely on that for quality.
- Restart the backend after adding, removing or renaming voice folders.

## Safety Rules

- Do not commit large RVC model files unless the user explicitly asks.
- Treat `.pth` files as executable-like model artifacts. Only use trusted sources.
- Do not remove Torch/RVC compatibility code without testing existing models.
- Keep the no-model path working: the pipeline must bypass RVC when no model is loaded.

## UI and API Behavior

- `/config` should list available RVC models for the frontend.
- Voice names should come from folder names.
- Changing model selection must keep frontend and backend payloads aligned.

## Validation

After RVC-related changes:

- Start backend and confirm logs list expected voices.
- Call or inspect `/config` and confirm the model appears.
- Select the model from the frontend.
- Verify output still returns within the 1s latency target when possible.
- Verify the pipeline still works with an empty `backend/voices/` directory.
