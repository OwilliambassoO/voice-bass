"""Ponto de entrada do Voice Bass: startup (lifespan), DI e montagem das rotas.

A construção dos adapters e da pipeline acontece no `lifespan`; as rotas vivem
em `api/`. Este módulo não contém lógica de domínio.
"""

import os

os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

import logging
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adapters.audioseal_adapter import AudioSealAdapter
from adapters.edge_tts_adapter import EdgeTTSAdapter
from adapters.rvc_adapter import RVCAdapter
from adapters.whisper_adapter import WhisperAdapter
from api.config_routes import router as config_router
from api.voice_websocket import websocket_voice
from services.voice_pipeline import VoicePipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

assert shutil.which("ffmpeg"), "FFmpeg não encontrado no PATH do processo."


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando pipeline de voz...")
    whisper = WhisperAdapter()
    audioseal = AudioSealAdapter.try_load()  # None se indisponível
    rvc = RVCAdapter()
    app.state.pipeline = VoicePipeline(whisper, EdgeTTSAdapter(), rvc, audioseal)
    logger.info("Aquecendo modelos (warm-up)...")
    await app.state.pipeline.warmup()
    logger.info("Servidor pronto.")
    yield
    # cleanup, se necessário, entra aqui


app = FastAPI(title="Voice Bass - Real-Time Voice Pipeline", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config_router)
app.add_api_websocket_route("/ws/voice", websocket_voice)

# Rota de métricas exposta só quando explicitamente habilitada (debug local).
if os.getenv("ENABLE_METRICS"):
    from api.metrics_routes import router as metrics_router

    app.include_router(metrics_router)
    logger.info("Endpoint /metrics habilitado (ENABLE_METRICS).")


@app.get("/")
async def root():
    return {"status": "ok", "message": "Voice Bass API está no ar."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
