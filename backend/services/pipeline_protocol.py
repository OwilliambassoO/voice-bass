"""Interface da pipeline de voz consumida pela camada de API.

Permite que rotas e testes dependam de um contrato leve (sem importar o
serviço concreto, que arrasta o stack de ML).
"""

from typing import Protocol

from domain.voice import VoiceModel


class PipelineProtocol(Protocol):
    def get_available_voices(self) -> list[VoiceModel]: ...

    def set_voice(self, voice: str) -> None: ...

    def set_rvc_model(self, model_name: str) -> None: ...

    async def transcribe_pcm(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str: ...

    async def synthesize_text(self, text: str) -> bytes: ...

    def get_metrics(self) -> dict: ...

    def note_dropped(self) -> None: ...
