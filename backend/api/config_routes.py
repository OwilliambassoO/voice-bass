"""Rota HTTP de configuração consumida pelo frontend na conexão inicial."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.dependencies import get_pipeline
from services.pipeline_protocol import PipelineProtocol

router = APIRouter()

VOICES = [
    {"id": "pt-BR-AntonioNeural", "label": "António (Masculino)"},
    {"id": "pt-BR-FranciscaNeural", "label": "Francisca (Feminino)"},
    {"id": "pt-BR-ThalitaNeural", "label": "Thalita (Feminino)"},
]

# Tempo de pausa (silêncio) que encerra um enunciado, exposto na UI no lugar do
# antigo buffer de latência. Aplicado por conexão na StreamingSession.
HANG_OPTIONS = [
    {"ms": 300, "label": "300ms (mais sensível)"},
    {"ms": 400, "label": "400ms"},
    {"ms": 500, "label": "500ms (padrão)"},
]


@router.get("/config")
async def get_config(pipeline: PipelineProtocol = Depends(get_pipeline)):
    """Retorna vozes TTS, opções de pausa (hangover) e modelos RVC disponíveis."""
    rvc_models = [
        {"id": v.name, "label": v.name}
        for v in pipeline.get_available_voices()
    ]
    return JSONResponse(content={
        "voices": VOICES,
        "hang_options": HANG_OPTIONS,
        "rvc_models": rvc_models,
    })
