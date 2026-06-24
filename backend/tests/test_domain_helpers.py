"""Testes dos helpers de domínio (sem ML, sem GPU)."""

import struct

from domain.audio import (
    AudioChunk,
    compute_rms,
    generate_silence_wav,
    pcm16_to_wav_bytes,
)


def test_pcm16_to_wav_header():
    pcm = b"\x01\x00\x02\x00"  # 2 amostras de 16 bits
    wav = pcm16_to_wav_bytes(pcm, 16000)

    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    # data size declarado no cabeçalho == len(pcm)
    declared_data = struct.unpack("<I", wav[40:44])[0]
    assert declared_data == len(pcm)
    # cabeçalho de 44 bytes + dados
    assert len(wav) == 44 + len(pcm)


def test_compute_rms_silence_is_zero():
    assert compute_rms(b"\x00\x00" * 100) == 0.0


def test_compute_rms_nonzero_for_signal():
    pcm = b"\xff\x7f" * 100  # amostras próximas do máximo positivo
    assert compute_rms(pcm) > 0.5


def test_generate_silence_duration():
    wav = generate_silence_wav(0.5, 16000)
    expected_data = int(16000 * 0.5) * 2  # samples * 2 bytes
    assert len(wav) == 44 + expected_data


def test_audio_chunk_duration():
    pcm = b"\x00\x00" * 16000  # 16000 amostras mono @ 16 kHz = 1.0 s
    chunk = AudioChunk(pcm, sample_rate=16000)
    assert abs(chunk.duration_s - 1.0) < 1e-9
