"""Orquestração do pipeline de conversão de voz em tempo real.

STT (Whisper) -> TTS (Edge-TTS) -> RVC -> AudioSeal.

A `VoicePipeline` recebe os adapters por injeção de dependências e não importa
bibliotecas de ML diretamente — a lógica de `process_chunk` é a mesma da
implementação monolítica anterior, apenas redistribuída.
"""

import asyncio
import logging
import os
import tempfile
import time
from statistics import mean

from adapters.voice_scanner import scan_voices
from domain.audio import (
    generate_silence_wav,
    pcm16_to_wav_bytes,
)
from domain.thresholds import (
    AVG_LOGPROB_THRESHOLD,
    DEFAULT_TTS_VOICE,
    NO_SPEECH_PROB_THRESHOLD,
)
from domain.voice import VoiceModel

logger = logging.getLogger(__name__)

# Etapas medidas por chunk. "total" cobre o pipeline inteiro.
_STAGES = ("stt", "tts", "rvc", "audioseal", "total")
_TIMINGS_WINDOW = 200  # janela deslizante de amostras por etapa


def _write_temp(data: bytes, suffix: str, registry: list[str]) -> str:
    f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    registry.append(f.name)
    f.write(data)
    f.close()
    return f.name


class VoicePipeline:
    """Pipeline com adapters injetados; modelos carregados uma única vez."""

    def __init__(
        self,
        whisper,
        tts,
        rvc,
        audioseal=None,
        voices_dir: str = "voices",
        scan=scan_voices,
    ):
        self.whisper = whisper
        self.tts = tts
        self.rvc = rvc
        self.audioseal = audioseal
        self.tts_voice = DEFAULT_TTS_VOICE
        self.voices_dir = voices_dir
        self._scan = scan
        self._voices_cache: list[VoiceModel] | None = None

        # Instrumentação de latência (Seção 6.6).
        self._timings: dict[str, list[float]] = {s: [] for s in _STAGES}
        self.dropped = 0

        voices = self.get_available_voices()
        if voices:
            self.set_rvc_model(voices[0].name)

        logger.info("Pipeline pronto.")

    def get_available_voices(self) -> list[VoiceModel]:
        self._voices_cache = self._scan(self.voices_dir)
        return self._voices_cache

    def set_rvc_model(self, model_name: str) -> None:
        """Carrega um modelo RVC pelo nome da pasta em voices_dir."""
        voices = self._voices_cache or self.get_available_voices()
        for v in voices:
            if v.name == model_name:
                self.rvc.load_model(v.pth_path, v.index_path)
                return
        raise ValueError(f"Modelo RVC '{model_name}' não encontrado.")

    def set_voice(self, voice: str) -> None:
        self.tts_voice = voice

    # ------------------------------------------------------------------
    # Instrumentação e métricas (Seção 6.6)
    # ------------------------------------------------------------------

    def _record(self, stage: str, seconds: float) -> None:
        buf = self._timings[stage]
        buf.append(seconds)
        if len(buf) > _TIMINGS_WINDOW:
            del buf[0]

    def note_dropped(self) -> None:
        """Registra um chunk descartado por sobrecarga (backpressure)."""
        self.dropped += 1

    def get_metrics(self) -> dict:
        """Média e p95 (em ms) por etapa, mais o total de descartes."""
        def _ms(value: float) -> float:
            return round(value * 1000, 1)

        def _p95(xs: list[float]) -> float | None:
            if not xs:
                return None
            ordered = sorted(xs)
            idx = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
            return _ms(ordered[idx])

        stages = {
            s: {
                "avg_ms": _ms(mean(self._timings[s])) if self._timings[s] else None,
                "p95_ms": _p95(self._timings[s]),
                "n": len(self._timings[s]),
            }
            for s in _STAGES
        }
        return {"stages": stages, "dropped": self.dropped}

    async def warmup(self) -> None:
        """Exercita os modelos com 1 s de silêncio para aquecer CUDA/JIT.

        Roda no startup (lifespan), antes do primeiro cliente, de modo que o
        primeiro chunk real não pague o custo de compilação/carga.
        """
        wav = generate_silence_wav(1.0, 16000)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(wav)
        tmp.close()
        try:
            await asyncio.to_thread(self.whisper.transcribe, tmp.name, "pt")
            if self.rvc.is_loaded:
                out = await asyncio.to_thread(self.rvc.infer, tmp.name)
                try:
                    os.remove(out)
                except OSError:
                    pass
            if self.audioseal is not None:
                out = await asyncio.to_thread(self.audioseal.apply, tmp.name)
                try:
                    os.remove(out)
                except OSError:
                    pass
            logger.info("Warm-up concluído.")
        except Exception as exc:  # noqa: BLE001 - warm-up é best-effort
            logger.warning("Warm-up falhou (seguindo mesmo assim): %s", exc)
        finally:
            try:
                os.remove(tmp.name)
            except OSError:
                pass

    async def transcribe_pcm(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcreve um buffer PCM 16-bit mono e devolve o texto limpo.

        Recebe o enunciado acumulado (não apenas 1s), de modo que o Whisper tem
        contexto suficiente para acertar. Aplica os filtros de confiança e
        devolve "" para não-fala/baixa confiança. O gate de silêncio e os
        limites de enunciado são responsabilidade da StreamingSession.
        """
        wav_bytes = pcm16_to_wav_bytes(pcm_bytes, sample_rate)
        temp_files: list[str] = []
        try:
            tmp_input = _write_temp(wav_bytes, ".wav", temp_files)

            t = time.perf_counter()
            result = await asyncio.to_thread(self.whisper.transcribe, tmp_input, "pt")
            self._record("stt", time.perf_counter() - t)

            segments = result.get("segments", [])
            if segments:
                seg = segments[0]
                no_speech = seg.get("no_speech_prob", 0)
                avg_logprob = seg.get("avg_logprob", 0)
                logger.info(
                    "Whisper seg: no_speech=%.2f, avg_logprob=%.2f",
                    no_speech, avg_logprob,
                )
                if no_speech > NO_SPEECH_PROB_THRESHOLD:
                    logger.info("Descartado: alta prob de não-fala (%.2f)", no_speech)
                    return ""
                if avg_logprob < AVG_LOGPROB_THRESHOLD:
                    logger.info(
                        "Descartado por baixa confiança (avg_logprob=%.2f): %s",
                        avg_logprob, result["text"].strip(),
                    )
                    return ""

            text = result["text"].strip()
            logger.info("STT: %s", text)
            return text

        finally:
            for p in temp_files:
                try:
                    os.remove(p)
                except OSError:
                    pass

    async def synthesize_text(self, text: str) -> bytes:
        """Sintetiza texto em voz (TTS -> RVC -> AudioSeal) e devolve WAV bytes.

        Chamado uma vez por enunciado (no fim da fala), de modo que o RVC roda
        uma vez por frase — voz coerente, em vez de pedaços de 1s.
        """
        t_total = time.perf_counter()
        temp_files: list[str] = []
        try:
            # 1 — TTS (Edge-TTS) — já é assíncrono nativamente
            tmp_tts = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
            temp_files.append(tmp_tts)
            t = time.perf_counter()
            await self.tts.synthesize(text, self.tts_voice, tmp_tts)
            self._record("tts", time.perf_counter() - t)

            # 2 — RVC — fora do event loop
            if self.rvc.is_loaded:
                t = time.perf_counter()
                tmp_rvc = await asyncio.to_thread(self.rvc.infer, tmp_tts)
                self._record("rvc", time.perf_counter() - t)
                temp_files.append(tmp_rvc)
            else:
                tmp_rvc = tmp_tts

            # 3 — AudioSeal watermark — fora do event loop
            if self.audioseal is not None:
                t = time.perf_counter()
                tmp_output = await asyncio.to_thread(self.audioseal.apply, tmp_rvc)
                self._record("audioseal", time.perf_counter() - t)
                temp_files.append(tmp_output)
            else:
                tmp_output = tmp_rvc

            with open(tmp_output, "rb") as f:
                output_bytes = f.read()

            self._record("total", time.perf_counter() - t_total)
            return output_bytes

        finally:
            for p in temp_files:
                try:
                    os.remove(p)
                except OSError:
                    pass
