"""Testes da StreamingSession com pipeline falso (sem ML).

Valida a lógica de acumular -> parcial -> finalizar no silêncio, sem depender
de Whisper/TTS/RVC.
"""

import asyncio

import numpy as np

from services.streaming_session import Final, Partial, StreamingSession

SR = 16000


class FakePipeline:
    def __init__(self):
        self.synth_calls: list[str] = []

    async def transcribe_pcm(self, pcm_bytes: bytes, sample_rate: int = SR) -> str:
        # Uma "palavra" por segundo acumulado: simula o texto crescendo com o
        # buffer (mínimo de 1 palavra para qualquer áudio não vazio).
        if not pcm_bytes:
            return ""
        seconds = max(1, len(pcm_bytes) // (SR * 2))
        return " ".join(["palavra"] * seconds)

    async def synthesize_text(self, text: str) -> bytes:
        self.synth_calls.append(text)
        return b"WAVDATA"


def _pcm(seconds: float, amplitude: int) -> bytes:
    n = int(seconds * SR)
    return np.full(n, amplitude, dtype=np.int16).tobytes()


def test_voiced_chunks_emit_growing_partials():
    pipe = FakePipeline()
    session = StreamingSession(pipe, sample_rate=SR)

    ev1 = asyncio.run(session.feed(_pcm(1, 8000)))
    ev2 = asyncio.run(session.feed(_pcm(1, 8000)))

    assert [type(e) for e in ev1] == [Partial]
    assert ev1[0].text == "palavra"
    assert ev2[0].text == "palavra palavra"  # buffer acumulou -> mais contexto
    assert pipe.synth_calls == []  # nada sintetizado durante a fala


def test_silence_finalizes_and_synthesizes_once():
    pipe = FakePipeline()
    session = StreamingSession(pipe, sample_rate=SR)

    asyncio.run(session.feed(_pcm(1, 8000)))
    final_events = asyncio.run(session.feed(_pcm(1, 0)))  # silêncio = fim do enunciado

    assert [type(e) for e in final_events] == [Final]
    assert final_events[0].audio == b"WAVDATA"
    assert pipe.synth_calls == ["palavra"]  # sintetiza uma vez, com o texto final


def test_silence_without_speech_is_noop():
    pipe = FakePipeline()
    session = StreamingSession(pipe, sample_rate=SR)

    assert asyncio.run(session.feed(_pcm(1, 0))) == []
    assert pipe.synth_calls == []


def test_mini_pause_within_chunk_finalizes():
    # Fala + pausa de 0.5s no MESMO chunk: com hangover curto (300ms) o enunciado
    # fecha sem esperar um chunk inteiro de silêncio.
    pipe = FakePipeline()
    session = StreamingSession(pipe, sample_rate=SR, silence_hang_ms=300)

    events = asyncio.run(session.feed(_pcm(0.5, 8000) + _pcm(0.5, 0)))

    assert any(isinstance(e, Final) for e in events)
    assert pipe.synth_calls  # sintetizou no fim da mini frase


def test_short_gap_below_hang_does_not_finalize():
    # Pausa de 0.3s (< 500ms) não encerra: segue acumulando e só emite parcial.
    pipe = FakePipeline()
    session = StreamingSession(pipe, sample_rate=SR, silence_hang_ms=500)

    events = asyncio.run(session.feed(_pcm(1, 8000) + _pcm(0.3, 0)))

    assert not any(isinstance(e, Final) for e in events)
    assert any(isinstance(e, Partial) for e in events)
    assert pipe.synth_calls == []
