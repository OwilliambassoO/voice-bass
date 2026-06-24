"""Helpers puros de áudio: empacotamento PCM<->WAV, silêncio e energia.

Depende apenas de numpy e da stdlib — sem stack de ML, para permitir testes
rápidos e sem GPU.
"""

import io
import struct
from dataclasses import dataclass

import numpy as np

PCM16_BYTES_PER_SAMPLE = 2


@dataclass(frozen=True)
class AudioChunk:
    """Um bloco de áudio PCM 16-bit recebido do frontend."""

    pcm: bytes
    sample_rate: int = 16000
    channels: int = 1

    @property
    def duration_s(self) -> float:
        denom = self.sample_rate * self.channels * PCM16_BYTES_PER_SAMPLE
        return len(self.pcm) / denom if denom else 0.0


def pcm16_to_wav_bytes(pcm_bytes: bytes, sample_rate: int, num_channels: int = 1) -> bytes:
    """Empacota PCM 16-bit raw em um buffer WAV completo (in-memory)."""
    data_size = len(pcm_bytes)
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)

    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))  # PCM
    buf.write(struct.pack("<H", num_channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", byte_rate))
    buf.write(struct.pack("<H", block_align))
    buf.write(struct.pack("<H", bits_per_sample))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm_bytes)
    return buf.getvalue()


def generate_silence_wav(duration_s: float, sample_rate: int = 16000) -> bytes:
    """Retorna WAV de silêncio com a duração especificada."""
    num_samples = int(sample_rate * duration_s)
    pcm = b"\x00\x00" * num_samples
    return pcm16_to_wav_bytes(pcm, sample_rate)


def compute_rms(pcm_bytes: bytes) -> float:
    """Energia RMS (0..1) de um buffer PCM 16-bit mono."""
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)))
