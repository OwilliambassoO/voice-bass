"""Sessão de transcrição em tempo real com buffer acumulado (por conexão).

Estratégia: acumula o áudio do enunciado em curso e re-transcreve o buffer
crescente a cada chunk, dando ao Whisper contexto suficiente para acertar
(janelas isoladas de 1s alucinam por falta de contexto). A cada chunk emite a
transcrição parcial; ao detectar uma pausa curta na fala (silêncio por um
"hangover" configurável), sintetiza a voz uma única vez com o texto final e
zera o buffer.

A detecção de fim de fala é feita em quadros de ~30ms — resolução mais fina que
o chunk — de modo que uma mini pausa fecha o enunciado mesmo no meio de um chunk
ou entre dois chunks (o silêncio acumulado persiste entre chamadas).

Mantém apenas estado por conexão; a transcrição e a síntese são delegadas ao
pipeline, e a sessão não conhece WebSocket/HTTP.
"""

import logging
from dataclasses import dataclass

from domain.audio import compute_rms
from domain.thresholds import SILENCE_RMS_THRESHOLD

logger = logging.getLogger(__name__)

# Duração máxima de um enunciado antes de forçar o fechamento. Protege o limite
# de ~30s do Whisper e evita buffer/latência sem limite na fala contínua.
_MAX_UTTERANCE_S = 15
# Silêncio contínuo (ms) que encerra o enunciado. Menor = reage a pausas mais
# curtas (mais responsivo), porém pode cortar em pausas naturais entre palavras.
_SILENCE_HANG_MS = 500
# Resolução da análise de silêncio. Quadros curtos detectam a pausa com precisão.
_FRAME_MS = 30
_BYTES_PER_SAMPLE = 2
# Crescimento mínimo de áudio (s) entre transcrições parciais. Desacopla o custo
# de STT do tamanho do chunk: a parcial re-transcreve ~1x/s mesmo com chunks de
# 250ms (que existem para detectar a pausa com baixa latência).
_PARTIAL_MIN_GROWTH_S = 1.0


@dataclass
class Partial:
    """Transcrição parcial do enunciado em curso (atualiza a linha ao vivo)."""

    text: str


@dataclass
class Final:
    """Fim do enunciado: texto consolidado e áudio sintetizado (WAV)."""

    text: str
    audio: bytes


class StreamingSession:
    def __init__(
        self,
        pipeline,
        sample_rate: int = 16000,
        silence_threshold: float = SILENCE_RMS_THRESHOLD,
        silence_hang_ms: float = _SILENCE_HANG_MS,
        max_utterance_s: float = _MAX_UTTERANCE_S,
        frame_ms: float = _FRAME_MS,
    ):
        self._pipeline = pipeline
        self._sample_rate = sample_rate
        self._silence_threshold = silence_threshold
        self._silence_hang_ms = silence_hang_ms
        self._max_bytes = int(max_utterance_s * sample_rate * _BYTES_PER_SAMPLE)
        self._frame_bytes = max(2, int(frame_ms / 1000 * sample_rate) * _BYTES_PER_SAMPLE)
        self._partial_min_bytes = int(_PARTIAL_MIN_GROWTH_S * sample_rate * _BYTES_PER_SAMPLE)

        self._buffer = bytearray()
        self._last_text = ""
        self._dirty = False  # fala nova ainda não transcrita no buffer
        self._trailing_silence_ms = 0.0  # silêncio contínuo no fim (entre chunks)
        self._last_partial_len = 0  # tamanho do buffer na última parcial transcrita

    def set_silence_hang_ms(self, ms: float) -> None:
        """Ajusta o tempo de pausa que encerra o enunciado (controle da UI)."""
        if 100 <= ms <= 2000:
            self._silence_hang_ms = float(ms)
            logger.info("Hangover de silêncio ajustado para %dms.", int(ms))

    def _frames(self, pcm_bytes: bytes):
        for i in range(0, len(pcm_bytes), self._frame_bytes):
            yield pcm_bytes[i:i + self._frame_bytes]

    async def feed(self, pcm_bytes: bytes) -> list[Partial | Final]:
        """Processa um chunk PCM e devolve os eventos a enviar ao cliente."""
        events: list[Partial | Final] = []
        voiced_added = False

        for frame in self._frames(pcm_bytes):
            final, voiced = await self._ingest_frame(frame)
            voiced_added = voiced_added or voiced
            if final is not None:
                events.append(final)
                voiced_added = False  # buffer foi zerado pela finalização

        capped = await self._enforce_cap()
        if capped is not None:
            events.append(capped)
            voiced_added = False

        partial = await self._maybe_partial(voiced_added)
        if partial is not None:
            events.append(partial)

        self._log_chunk(pcm_bytes)
        return events

    async def _ingest_frame(self, frame: bytes) -> tuple["Final | None", bool]:
        """Acumula um quadro; devolve (Final|None, houve_voz_neste_quadro)."""
        if compute_rms(frame) >= self._silence_threshold:
            self._buffer.extend(frame)
            self._trailing_silence_ms = 0.0
            self._dirty = True
            return None, True

        # Silêncio sem enunciado ativo: ignora.
        if not self._buffer:
            return None, False

        # Silêncio dentro de um enunciado: preserva a pausa curta no buffer
        # (contexto p/ Whisper) e conta o silêncio do fim até o hangover.
        self._buffer.extend(frame)
        self._trailing_silence_ms += (len(frame) // _BYTES_PER_SAMPLE) / self._sample_rate * 1000
        if self._trailing_silence_ms >= self._silence_hang_ms:
            return await self._finalize(), False
        return None, False

    async def _enforce_cap(self) -> "Final | None":
        """Fecha à força um enunciado longo demais (fala contínua sem pausa)."""
        if self._buffer and len(self._buffer) >= self._max_bytes:
            return await self._finalize()
        return None

    async def _maybe_partial(self, voiced_added: bool) -> "Partial | None":
        """Re-transcreve o buffer para uma parcial, no máximo ~1x/s.

        Só transcreve quando houve fala nova e o buffer cresceu o suficiente
        desde a última parcial — assim chunks pequenos (250ms) dão detecção de
        pausa fina sem multiplicar o custo de STT.
        """
        if not (self._buffer and voiced_added):
            return None
        if len(self._buffer) - self._last_partial_len < self._partial_min_bytes:
            return None

        self._last_partial_len = len(self._buffer)
        text = await self._pipeline.transcribe_pcm(bytes(self._buffer), self._sample_rate)
        if not text:
            return None
        self._last_text = text
        self._dirty = False
        return Partial(text)

    def _log_chunk(self, pcm_bytes: bytes) -> None:
        logger.info(
            "Chunk: RMS=%.4f trailing_silence=%dms (limiar=%.4f, hang=%dms)",
            compute_rms(pcm_bytes), self._trailing_silence_ms,
            self._silence_threshold, self._silence_hang_ms,
        )

    async def _finalize(self) -> Final | None:
        """Fecha o enunciado: sintetiza o texto consolidado e zera o estado."""
        buffer = bytes(self._buffer)
        text = self._last_text
        dirty = self._dirty
        self._reset()
        if not buffer:
            return None
        # Se houve fala não transcrita (pausa logo após falar), re-transcreve o
        # buffer completo para o texto final refletir o enunciado inteiro.
        if dirty or not text:
            text = await self._pipeline.transcribe_pcm(buffer, self._sample_rate)
        if not text:
            return None
        audio = await self._pipeline.synthesize_text(text)
        return Final(text, audio)

    def _reset(self) -> None:
        self._buffer = bytearray()
        self._last_text = ""
        self._dirty = False
        self._trailing_silence_ms = 0.0
        self._last_partial_len = 0
