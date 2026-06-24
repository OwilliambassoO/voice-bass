"""Endpoint WebSocket /ws/voice: protocolo de áudio e configuração.

Mensagens de texto carregam JSON de controle (config/ping); mensagens binárias
carregam chunks PCM16. A transcrição acumulada (StreamingSession) responde com
mensagens de transcrição parcial (partial=true) e, no fim de cada enunciado,
com a transcrição final (partial=false) seguida do WAV sintetizado.
"""

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from services.pipeline_protocol import PipelineProtocol
from services.streaming_session import Final, Partial, StreamingSession

logger = logging.getLogger(__name__)


async def _handle_text_message(
    ws: WebSocket, pipeline: PipelineProtocol, session: StreamingSession, raw: str
) -> None:
    data = json.loads(raw)
    action = data.get("action")

    if action == "config":
        voice = data.get("voice", "pt-BR-AntonioNeural")
        pipeline.set_voice(voice)

        rvc_model = data.get("rvc_model")
        if rvc_model:
            try:
                pipeline.set_rvc_model(rvc_model)
            except ValueError as e:
                logger.warning("Modelo RVC inválido: %s", e)

        hang_ms = data.get("hang_ms")
        if hang_ms is not None:
            session.set_silence_hang_ms(hang_ms)

        await ws.send_text(json.dumps({
            "type": "config_ack",
            "voice": voice,
            "rvc_model": rvc_model,
            "hang_ms": hang_ms,
        }))
        logger.info(
            "Configuração atualizada: voice=%s, rvc_model=%s, hang_ms=%s",
            voice, rvc_model, hang_ms,
        )
    elif action == "ping":
        await ws.send_text(json.dumps({"type": "pong"}))


async def _handle_audio_chunk(ws: WebSocket, session: StreamingSession, pcm_data: bytes) -> None:
    try:
        for event in await session.feed(pcm_data):
            if isinstance(event, Partial):
                await ws.send_text(json.dumps({
                    "type": "transcription", "text": event.text, "partial": True,
                }))
            elif isinstance(event, Final):
                await ws.send_text(json.dumps({
                    "type": "transcription", "text": event.text, "partial": False,
                }))
                await ws.send_bytes(event.audio)
    except Exception as e:
        logger.error("Erro no pipeline: %s", e, exc_info=True)
        await ws.send_text(json.dumps({"type": "error", "message": str(e)}))


async def _process_worker(ws: WebSocket, session: StreamingSession, queue: asyncio.Queue) -> None:
    """Consome chunks da fila em ordem e alimenta a sessão de transcrição.

    Único consumidor: preserva a ordem dos chunks e garante que apenas um
    chunk é processado por vez (o buffer da sessão não é reentrante).
    """
    while True:
        pcm_data = await queue.get()
        try:
            await _handle_audio_chunk(ws, session, pcm_data)
        finally:
            queue.task_done()


async def websocket_voice(ws: WebSocket) -> None:
    pipeline: PipelineProtocol = ws.app.state.pipeline
    await ws.accept()
    logger.info("Cliente WebSocket conectado.")

    # Estado de transcrição acumulada, isolado por conexão.
    session = StreamingSession(pipeline)

    # Fila ilimitada, sem descarte: cada chunk recebido é processado em ordem,
    # custe o tempo que custar (decisão de protótipo — capturar a frase inteira
    # tem prioridade sobre o alvo de ≤1s de atraso). Em CUDA o worker drena em
    # tempo real; em CPU a saída atrasa mas nenhum trecho de fala é perdido.
    # A recepção fica desacoplada do processamento: enquanto um chunk roda no
    # pipeline, os próximos aguardam na fila em vez de serem descartados.
    queue: asyncio.Queue[bytes] = asyncio.Queue()
    worker = asyncio.create_task(_process_worker(ws, session, queue))

    try:
        while True:
            message = await ws.receive()
            if "text" in message:
                await _handle_text_message(ws, pipeline, session, message["text"])
            elif "bytes" in message and message["bytes"]:
                queue.put_nowait(message["bytes"])
    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado.")
    except Exception as e:
        logger.error("Erro na conexão WebSocket: %s", e, exc_info=True)
    finally:
        worker.cancel()
