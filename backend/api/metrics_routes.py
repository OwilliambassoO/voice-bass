"""Rota de métricas de latência (debug local).

Registrada apenas quando a variável de ambiente `ENABLE_METRICS` está ativa
(ver `main.py`), para não expor a rota em produção.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.dependencies import get_pipeline
from services.pipeline_protocol import PipelineProtocol

router = APIRouter()


@router.get("/metrics")
async def get_metrics(pipeline: PipelineProtocol = Depends(get_pipeline)):
    """Média e p95 por etapa do pipeline, mais o total de chunks descartados."""
    return JSONResponse(content=pipeline.get_metrics())
